"""
Sovereign Cache Module

This module provides an extensible cache backend system that allows clients
to configure their own remote cache backends through entry points.
"""

import asyncio
import threading

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
        id = client_id(req)
        if result := self.try_read(id):
            if result.from_remote:
                self.register_async(req)
                # Write back to filesystem
                self.local.set(id, result.value)
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
        # Set a bound so that we don't try for eternity
        # Realistically this should succeed eventually
        # and reaching 30 should never happen unless worker is completely dead
        def job():
            attempts = 30
            while attempts:
                if self.register_over_http(req):
                    return
                attempts -= 1

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
            stats.increment("cache.fs.write.success")
            cached = True
        except Exception as e:
            log.warning(f"Failed to write to filesystem cache: {e}")
            msg.append(("warning", f"Failed to write to filesystem cache: {e}"))
            stats.increment("cache.fs.write.error")
        if self.remote:
            try:
                self.remote.set(key, value, timeout)
                stats.increment("cache.remote.write.success")
                cached = True
            except Exception as e:
                log.warning(f"Failed to write to remote cache: {e}")
                msg.append(("warning", f"Failed to write to remote cache: {e}"))
                stats.increment("cache.remote.write.error")
        return cached, msg


def client_id(req: DiscoveryRequest) -> str:
    return req.cache_key(config.cache.hash_rules)
