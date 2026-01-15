"""
Sovereign Cache Module

This module provides an extensible cache backend system that allows clients
to configure their own remote cache backends through entry points.
"""

import asyncio
import os
import threading
import time

import requests
from typing_extensions import final

from sovereign import WORKER_URL, stats
from sovereign import application_logger as log
from sovereign.cache.backends import CacheBackend, get_backend
from sovereign.cache.filesystem import FilesystemCache
from sovereign.cache.types import CacheResult, Entry
from sovereign.configuration import config
from sovereign.types import DiscoveryRequest, RegisterClientRequest

CACHE_READ_TIMEOUT = config.cache.read_timeout
REMOTE_TTL = 300  # 5 minutes - TTL for entries read from remote cache


class CacheManagerBase:
    def __init__(self) -> None:
        self.local: FilesystemCache = FilesystemCache()
        self.remote: CacheBackend | None = get_backend()
        if self.remote is None:
            log.info("Cache initialized with filesystem backend only")
        else:
            log.info("Cache initialized with filesystem and remote backends")

    # Client Id registration

    def register(self, req: DiscoveryRequest):
        id = client_id(req)
        log.debug(f"Registering client {id}")
        self.local.register(id, req)
        stats.increment("client.registration", tags=["status:registered"])
        return id, req

    def registered(self, req: DiscoveryRequest) -> bool:
        ret = False
        id = client_id(req)
        if value := self.local.registered(id):
            ret = value
        log.debug(f"Client {id} registered={ret}")
        return ret

    def get_registered_clients(self) -> list[tuple[str, DiscoveryRequest]]:
        if value := self.local.get_registered_clients():
            return value
        return []


@final
class CacheReader(CacheManagerBase):
    def try_read(self, key: str) -> CacheResult | None:
        # Try filesystem first
        if value := self.local.get(key):
            stats.increment("cache.fs.hit")
            return CacheResult(value=value, from_remote=False)
        stats.increment("cache.fs.miss")

        # Fallback to remote cache if available
        if self.remote:
            try:
                if value := self.remote.get(key):
                    ret = CacheResult(value=value, from_remote=True)
                    stats.increment("cache.remote.hit")
                    return ret
            except Exception as e:
                log.warning(f"Failed to read from remote cache: {e}")
                stats.increment("cache.remote.error")
            stats.increment("cache.remote.miss")
            log.warning(f"Failed to read from either cache for {key}")
        return None

    def get(self, req: DiscoveryRequest) -> Entry | None:
        """Read from cache, writing back from remote with short TTL if needed.

        Flow:
          1. Entry read from remote → cached with 300s TTL
          2. Background registration triggers worker to generate fresh config
          3. Remote entry expires after 300s
          4. Next request gets worker-generated config (cached infinitely)
        """
        id = client_id(req)
        if result := self.try_read(id):
            if result.from_remote:
                # Write immediately with short TTL to prevent empty cache window
                self.local.set(id, result.value, timeout=REMOTE_TTL)
                log.info(
                    f"Cache writeback from remote: client_id={id} version={result.value.version} "
                    f"ttl={REMOTE_TTL} type=remote pid={os.getpid()}"
                )
                stats.increment("cache.fs.writeback", tags=["type:remote"])

                # Background thread triggers worker to generate fresh config
                self.register_async(req)
            return result.value
        return None

    @stats.timed("cache.read_ms")
    async def blocking_read(
        self, req: DiscoveryRequest, timeout_s=CACHE_READ_TIMEOUT, poll_interval_s=0.5
    ) -> Entry | None:
        cid = client_id(req)
        metric = "client.registration"
        if entry := self.get(req):
            return entry

        log.info(f"Cache entry not found for {cid}, registering and waiting")
        registered = False
        start = asyncio.get_event_loop().time()
        attempt = 1
        while (asyncio.get_event_loop().time() - start) < timeout_s:
            if not registered:
                try:
                    if self.register_over_http(req):
                        stats.increment(metric, tags=["status:registered"])
                        registered = True
                        log.info(f"Client {cid} registered")
                    else:
                        stats.increment(metric, tags=["status:ratelimited"])
                        await asyncio.sleep(min(attempt, CACHE_READ_TIMEOUT))
                        attempt *= 2
                except Exception as e:
                    stats.increment(metric, tags=["status:failed"])
                    log.exception(f"Tried to register client but failed: {e}")
            if entry := self.get(req):
                log.info(f"Entry has been populated for {cid}")
                return entry
            await asyncio.sleep(poll_interval_s)

        return None

    def register_over_http(self, req: DiscoveryRequest) -> bool:
        registration = RegisterClientRequest(request=req)
        log.debug(f"Sending registration to worker for {req}")
        try:
            response = requests.put(
                f"{WORKER_URL}/client",
                json=registration.model_dump(),
                timeout=3,
            )
            match response.status_code:
                case 200 | 202:
                    log.debug("Worker responded OK to registration")
                    return True
                case code:
                    log.debug(f"Worker responded with {code} to registration")
        except Exception as e:
            log.exception(f"Error while registering client: {e}")
        return False

    def register_async(self, req: DiscoveryRequest):
        """Register client async to trigger worker to generate fresh config.

        Registration tells the worker about this client so it generates fresh config.
        """

        def job():
            start_time = time.time()
            attempts = 5
            backoff = 1.0
            attempt_num = 0

            while attempts:
                attempt_num += 1
                if self.register_over_http(req):
                    duration_ms = (time.time() - start_time) * 1000
                    stats.increment(
                        "client.registration.async",
                        tags=["status:success", f"attempts:{attempt_num}"],
                    )
                    stats.timing("client.registration.async.duration_ms", duration_ms)
                    log.debug(f"Async registration succeeded: attempts={attempt_num}")
                    return
                attempts -= 1
                if attempts:
                    log.debug(
                        f"Async registration failed: retrying_in={backoff}s remaining={attempts}"
                    )
                    time.sleep(backoff)
                    backoff *= 2

            # Registration failed - entry stays at REMOTE_TTL, will expire and retry
            duration_ms = (time.time() - start_time) * 1000
            stats.increment("client.registration.async", tags=["status:exhausted"])
            stats.timing("client.registration.async.duration_ms", duration_ms)
            log.warning(
                f"Async registration exhausted for {req}: remote entry will expire "
                f"in {REMOTE_TTL}s and retry"
            )

        t = threading.Thread(target=job)
        t.start()


@final
class CacheWriter(CacheManagerBase):
    def set(
        self, key: str, value: Entry, timeout: int | None = None
    ) -> tuple[bool, list[tuple[str, str]]]:
        msg = []
        cached = False
        try:
            self.local.set(key, value, timeout)
            log.info(
                f"Cache write to filesystem: client_id={key} version={value.version} "
                f"ttl={timeout} pid={os.getpid()} thread_id={threading.get_ident()}"
            )
            stats.increment("cache.fs.write.success")
            cached = True
        except Exception as e:
            log.warning(
                f"Failed to write to filesystem cache: client_id={key} error={e}"
            )
            msg.append(("warning", f"Failed to write to filesystem cache: {e}"))
            stats.increment("cache.fs.write.error")
        if self.remote:
            try:
                self.remote.set(key, value, timeout)
                log.info(
                    f"Cache write to remote: client_id={key} version={value.version} "
                    f"ttl={timeout} pid={os.getpid()} thread_id={threading.get_ident()}"
                )
                stats.increment("cache.remote.write.success")
                cached = True
            except Exception as e:
                log.warning(
                    f"Failed to write to remote cache: client_id={key} error={e}"
                )
                msg.append(("warning", f"Failed to write to remote cache: {e}"))
                stats.increment("cache.remote.write.error")
        return cached, msg


def client_id(req: DiscoveryRequest) -> str:
    return req.cache_key(config.cache.hash_rules)
