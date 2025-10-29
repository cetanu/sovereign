"""
Sovereign Cache Module

This module provides an extensible cache backend system that allows clients
to configure their own remote cache backends through entry points.
"""

import uuid
import asyncio
import threading
from contextlib import asynccontextmanager

import requests
from pydantic import BaseModel

from sovereign import config, stats, application_logger as log
from sovereign.schemas import DiscoveryRequest, Node, RegisterClientRequest
from sovereign.cache.backends import get_backend
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


class DualCache:
    """Cache that writes to both filesystem and remote backend, reads filesystem first with remote fallback"""

    def __init__(self, fs_cache: FilesystemCache, remote_cache):
        self.fs_cache = fs_cache
        self.remote_cache = remote_cache

    def get(self, key):
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


# TODO: implement lock-free client registration
@asynccontextmanager
async def lock():
    token = str(uuid.uuid4())
    poll_interval = 0.2
    acquired = False
    try:
        while not acquired:
            existing = manager.get(CLIENTS_LOCK)
            if not existing:
                manager.set(CLIENTS_LOCK, token, timeout=5)
                acquired = True
                log.debug("Lock acquired")
            else:
                log.debug("Waiting to acquire lock")
                await asyncio.sleep(poll_interval)
        yield
    finally:
        if manager.get(CLIENTS_LOCK) == token:
            manager.set(CLIENTS_LOCK, None, timeout=0)
            log.debug("Lock freed")


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
    return str(req.cache_key(config.cache.hash_rules))


def clients() -> list[tuple[str, DiscoveryRequest]]:
    return manager.get(CLIENTS_KEY) or []


async def register(req: DiscoveryRequest) -> tuple[str, DiscoveryRequest]:
    id = client_id(req)
    log.debug(f"Registering client {id}")
    async with lock():
        existing = clients()
        existing.append((id, req))
        manager.set(CLIENTS_KEY, existing)
        log.debug(f"Registered client {id}")
    return id, req


def registered(req: DiscoveryRequest) -> bool:
    item = (client_id(req), req)
    return item in clients()


manager = CacheManager()
