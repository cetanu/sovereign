"""
Sovereign Cache Module

This module provides an extensible cache backend system that allows clients
to configure their own remote cache backends through entry points.
"""

import asyncio
import importlib
from typing import Any
from typing_extensions import final

import requests

from sovereign import stats, application_logger as log
from sovereign.types import DiscoveryRequest, RegisterClientRequest
from sovereign.configuration import config
from sovereign.cache.types import Entry, CacheResult
from sovereign.cache.backends import get_backend
from sovereign.cache.filesystem import FilesystemCache


CACHE_READ_TIMEOUT = config.cache.read_timeout
WORKER_URL = "http://localhost:9080/client"


@final
class CacheManager:
    def __init__(self):
        self.local = FilesystemCache()
        self.remote = get_backend()
        if self.remote is None:
            log.info("Cache initialized with filesystem backend only")
        else:
            log.info("Cache initialized with filesystem and remote backends")

    def try_read(self, key: str) -> CacheResult | None:
        # Try filesystem first
        if value := self.local.get(key):
            stats.increment("cache.fs.hit")
            return CacheResult(value=value, from_remote=False)

        # Fallback to remote cache if available
        if self.remote:
            try:
                if value := self.remote.get(key):
                    ret = CacheResult(value=value, from_remote=True)
                    # Write back to filesystem
                    self.local.set(key, value)
                    stats.increment("cache.remote.hit")
                    return ret
            except Exception as e:
                log.warning(f"Failed to read from remote cache: {e}")
                stats.increment("cache.remote.error")

        return None

    def get(self, req: DiscoveryRequest) -> Entry | None:
        id = client_id(req)
        if result := self.try_read(id):
            try:
                # FIXME: why is this the wrong type
                if result.from_remote or not self.registered(req):
                    _ = self.register(req)
                return result.value
            except Exception as e:
                if config.sentry_dsn:
                    mod = importlib.import_module("sentry_sdk")
                    mod.capture_exception(e)
        return None

    def set(self, key, value, timeout=None):
        try:
            stats.increment("cache.fs.write.success")
            self.local.set(key, value, timeout)
        except Exception as e:
            log.warning(f"Failed to write to filesystem cache: {e}")
            stats.increment("cache.fs.write.error")
        if self.remote:
            try:
                self.remote.set(key, value, timeout)
                stats.increment("cache.remote.write.success")
            except Exception as e:
                log.warning(f"Failed to write to remote cache: {e}")
                stats.increment("cache.remote.write.error")

    def register(self, req: DiscoveryRequest):
        id = client_id(req)
        log.debug(f"Registering client {id}")
        self.local.register(id, req)
        return id, req

    def registered(self, req: DiscoveryRequest) -> bool:
        id = client_id(req)
        if value := self.local.registered(id):
            ret = value
        ret = False
        log.debug(f"Client {id} registered={ret}")
        return ret

    def get_registered_clients(self) -> list[tuple[str, Any]]:
        if value := self.local.get_registered_clients():
            return value
        return []


@stats.timed("cache.read_ms")
async def blocking_read(
    req: DiscoveryRequest, timeout_s=CACHE_READ_TIMEOUT, poll_interval_s=0.5
) -> Entry | None:
    metric = "client.registration"
    if entry := read(req):
        return entry

    registered = False
    registration = RegisterClientRequest(request=req)
    start = asyncio.get_event_loop().time()
    attempt = 1
    while (asyncio.get_event_loop().time() - start) < timeout_s:
        if not registered:
            try:
                response = requests.put(WORKER_URL, json=registration.model_dump())
                match response.status_code:
                    case 200 | 202:
                        stats.increment(metric, tags=["status:registered"])
                        registered = True
                    case 429:
                        stats.increment(metric, tags=["status:ratelimited"])
                        await asyncio.sleep(min(attempt, CACHE_READ_TIMEOUT))
                        attempt *= 2
            except Exception as e:
                stats.increment(metric, tags=["status:failed"])
                log.exception(f"Tried to register client but failed: {e}")
        if entry := read(req):
            return entry
        await asyncio.sleep(poll_interval_s)

    return None


def client_id(req: DiscoveryRequest) -> str:
    return req.cache_key(config.cache.hash_rules)


manager = CacheManager()
# Old API for compat
write = manager.set
read = manager.get
clients = manager.get_registered_clients
register = manager.register
registered = manager.registered
