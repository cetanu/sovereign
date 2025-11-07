"""
Sovereign Cache Module

This module provides an extensible cache backend system that allows clients
to configure their own remote cache backends through entry points.
"""

import asyncio
import threading
from typing import Any
from typing_extensions import final

import requests

from sovereign import stats, application_logger as log
from sovereign.schemas import config, DiscoveryRequest, RegisterClientRequest
from sovereign.cache.types import Entry, CacheResult
from sovereign.cache.backends import CacheBackend, get_backend
from sovereign.cache.filesystem import FilesystemCache

CLIENTS_LOCK = "sovereign_clients_lock"
CLIENTS_KEY = "sovereign_clients"
CACHE_READ_TIMEOUT = config.cache.read_timeout
WORKER_URL = "http://localhost:9080/client"


@final
class DualCache:
    """Cache that writes to both filesystem and remote backend, reads filesystem first with remote fallback"""

    def __init__(self, fs_cache: FilesystemCache, remote_cache: CacheBackend | None):
        self.fs_cache = fs_cache
        self.remote_cache = remote_cache

    def get(self, key: str) -> CacheResult | None:
        # Try filesystem first
        if value := self.fs_cache.get(key):
            stats.increment("cache.fs.hit")
            return CacheResult(value=value, from_remote=False)

        # Fallback to remote cache if available
        if self.remote_cache:
            try:
                if value := self.remote_cache.get(key):
                    stats.increment("cache.remote.hit")
                    # Write back to filesystem
                    self.fs_cache.set(key, value)
                    return CacheResult(value=value, from_remote=True)
            except Exception as e:
                log.warning(f"Failed to read from remote cache: {e}")
                stats.increment("cache.remote.error")

        return None

    def set(self, key, value, timeout=None):
        self.fs_cache.set(key, value, timeout)
        if self.remote_cache:
            try:
                self.remote_cache.set(key, value, timeout)
                stats.increment("cache.remote.write.success")
            except Exception as e:
                log.warning(f"Failed to write to remote cache: {e}")
                stats.increment("cache.remote.write.error")

    def register(self, id: str, req: DiscoveryRequest):
        self.fs_cache.register(id, req)

    def registered(self, id: str) -> bool:
        if value := self.fs_cache.registered(id):
            return value
        return False

    def get_registered_clients(self) -> list[tuple[str, Any]]:
        if value := self.fs_cache.get_registered_clients():
            return value
        return []


class CacheManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        filesystem_cache = FilesystemCache()
        remote_cache = get_backend()

        if remote_cache is None:
            log.info("Cache initialized with filesystem backend only")
        else:
            log.info("Cache initialized with filesystem and remote backends")
        self._cache = DualCache(filesystem_cache, remote_cache)
        self._initialized = True

    def get(self, req: DiscoveryRequest) -> Entry | None:
        id = client_id(req)
        if result := self._cache.get(id):
            try:
                # FIXME: why is this the wrong type
                assert isinstance(result, CacheResult)
                if result.from_remote:
                    self.register(req)
                stats.increment("cache.hit")
                return result.value
            except AssertionError:
                pass
        stats.increment("cache.miss")
        return None

    def set(self, key: str, value: Entry, timeout: int | None = None) -> None:
        return self._cache.set(key, value, timeout)

    def register(self, req: DiscoveryRequest) -> tuple[str, DiscoveryRequest]:
        """Register a client using the cache backend"""
        id = client_id(req)
        log.debug(f"Registering client {id}")
        self._cache.register(id, req)
        return id, req

    def registered(self, req: DiscoveryRequest) -> bool:
        """Check if a client is registered using the cache backend"""
        id = client_id(req)
        is_registered = self._cache.registered(id)
        log.debug(f"Client {id} registered={is_registered}")
        return is_registered

    def get_registered_clients(self) -> list[tuple[str, Any]]:
        """Get all registered clients using the cache backend"""
        return self._cache.get_registered_clients()


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

# Old APIs
write = manager.set
read = manager.get
clients = manager.get_registered_clients
register = manager.register
registered = manager.registered
