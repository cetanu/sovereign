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
from pydantic import BaseModel

from sovereign import stats, application_logger as log
from sovereign.schemas import config, DiscoveryRequest, Node, RegisterClientRequest
from sovereign.cache.backends import CacheBackend, get_backend
from sovereign.cache.filesystem import FilesystemCache

CLIENTS_LOCK = "sovereign_clients_lock"
CLIENTS_KEY = "sovereign_clients"
CACHE_READ_TIMEOUT = config.cache.read_timeout
WORKER_URL = "http://localhost:9080/client"


class Entry(BaseModel):
    text: str
    len: int
    version: str
    node: Node


@final
class DualCache:
    """Cache that writes to both filesystem and remote backend, reads filesystem first with remote fallback"""

    def __init__(self, fs_cache: FilesystemCache, remote_cache: CacheBackend):
        self.fs_cache = fs_cache
        self.remote_cache = remote_cache

    def get(self, key: str) -> Any:
        # Try filesystem first
        if value := self.fs_cache.get(key):
            stats.increment("cache.fs.hit")
            return value

        # Fallback to remote cache if available
        if self.remote_cache:
            try:
                if value := self.remote_cache.get(key):
                    stats.increment("cache.remote.hit")
                    # Write back to filesystem
                    self.fs_cache.set(key, value)
                    return value
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

    def delete(self, key):
        fs_result = self.fs_cache.delete(key)
        remote_result = True

        if self.remote_cache:
            try:
                if hasattr(self.remote_cache, "delete"):
                    remote_result = self.remote_cache.delete(key)
                else:
                    # Fallback for backends without delete
                    self.remote_cache.set(key, None, timeout=0)
            except Exception as e:
                log.warning(f"Failed to delete from remote cache: {e}")
                remote_result = False

        return fs_result and remote_result

    def register(self, id: str, req: DiscoveryRequest):
        self.fs_cache.register(id, req)
        if self.remote_cache:
            try:
                self.remote_cache.register(id, req)
            except Exception as e:
                log.warning(f"Failed to register client in remote cache: {e}")

    def registered(self, id: str) -> bool:
        if value := self.fs_cache.registered(id):
            return value

        if self.remote_cache:
            try:
                return self.remote_cache.registered(id)
            except Exception as e:
                log.warning(f"Failed to check registration in remote cache: {e}")
        return False

    def get_registered_clients(self) -> list[tuple[str, Any]]:
        if value := self.fs_cache.get_registered_clients():
            return value

        if self.remote_cache:
            try:
                return self.remote_cache.get_registered_clients()
            except Exception as e:
                log.warning(f"Failed to get clients from remote cache: {e}")
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
            self._cache = filesystem_cache
            log.info("Cache initialized with filesystem backend only")
        else:
            self._cache = DualCache(filesystem_cache, remote_cache)
            log.info("Cache initialized with filesystem and remote backends")
        self._initialized = True

    def get(self, key):
        return self._cache.get(key)

    def set(self, key, value, timeout=None):
        return self._cache.set(key, value, timeout)

    def delete(self, key):
        if hasattr(self._cache, "delete"):
            return self._cache.delete(key)
        # Fallback for caches that don't implement delete
        return self._cache.set(key, None, timeout=0)

    def register(self, client_id: str, client_data):
        """Register a client using the cache backend"""
        return self._cache.register(client_id, client_data)

    def registered(self, client_id: str) -> bool:
        """Check if a client is registered using the cache backend"""
        return self._cache.registered(client_id)

    def get_registered_clients(self) -> list[tuple[str, Any]]:
        """Get all registered clients using the cache backend"""
        return self._cache.get_registered_clients()


@stats.timed("cache.read_ms")
async def blocking_read(
    req: DiscoveryRequest, timeout=CACHE_READ_TIMEOUT, poll_interval=0.5
) -> Entry | None:
    metric = "client.registration"
    id = client_id(req)
    if entry := read(id):
        return entry

    registered = False
    registration = RegisterClientRequest(request=req)
    start = asyncio.get_event_loop().time()
    attempt = 1
    while (asyncio.get_event_loop().time() - start) < timeout:
        if not registered:
            try:
                response = requests.put(WORKER_URL, json=registration.model_dump())
                match response.status_code:
                    case 200 | 202:
                        registered = True
                    case 429:
                        stats.increment(metric, tags=["status:ratelimited"])
                        await asyncio.sleep(min(attempt, CACHE_READ_TIMEOUT))
                        attempt *= 2
            except Exception as e:
                stats.increment(metric, tags=["status:failed"])
                log.exception(f"Tried to register client but failed: {e}")
        if entry := read(id):
            return entry
        await asyncio.sleep(poll_interval)

    return None


def read(id: str) -> Entry | None:
    if entry := manager.get(id):
        stats.increment("cache.hit")
        return entry
    stats.increment("cache.miss")
    return None


def write(id: str, val: Entry) -> None:
    manager.set(id, val)


def client_id(req: DiscoveryRequest) -> str:
    return req.cache_key(config.cache.hash_rules)


def clients() -> list[tuple[str, DiscoveryRequest]]:
    return manager.get_registered_clients()


async def register(req: DiscoveryRequest) -> tuple[str, DiscoveryRequest]:
    id = client_id(req)
    log.debug(f"Registering client {id}")
    manager.register(id, req)
    log.debug(f"Registered client {id}")
    return id, req


def registered(req: DiscoveryRequest) -> bool:
    """Check if a client is registered using the cache backend"""
    id = client_id(req)
    is_registered = manager.registered(id)
    log.debug(f"Client {id} registered={is_registered}")
    return is_registered


manager = CacheManager()
