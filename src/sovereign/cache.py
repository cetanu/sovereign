import uuid
import asyncio
import importlib
from hashlib import blake2s
from typing import Optional
from contextlib import asynccontextmanager

import requests
from pydantic import BaseModel
from cachelib import FileSystemCache, RedisCache, BaseCache

from sovereign import config, stats, application_logger as log
from sovereign.schemas import DiscoveryRequest, Node, RegisterClientRequest


CLIENTS_LOCK = "sovereign_clients_lock"
CLIENTS_KEY = "sovereign_clients"
CACHE: BaseCache
CACHE_READ_TIMEOUT = config.cache_timeout
WORKER_URL = "http://localhost:9080/client"

redis = config.discovery_cache
if redis.enabled:
    if mod := importlib.import_module("redis"):
        try:
            CACHE = RedisCache(
                host=mod.Redis(
                    host=redis.host,
                    port=redis.port,
                    password=redis.password.get_secret_value(),
                    ssl=redis.secure,
                    db=0,
                ),
                key_prefix="discovery_request_",
                default_timeout=redis.ttl,
            )
        except Exception as e:
            log.exception(f"Tried to use redis for caching: {e}")
else:
    CACHE = FileSystemCache(config.cache_path, default_timeout=0, hash_method=blake2s)


class Entry(BaseModel):
    text: str
    len: int
    version: str
    node: Node


@asynccontextmanager
async def lock():
    token = str(uuid.uuid4())
    poll_interval = 0.2
    acquired = False
    try:
        while not acquired:
            existing = CACHE.get(CLIENTS_LOCK)
            if not existing:
                CACHE.set(CLIENTS_LOCK, token, timeout=5)
                acquired = True
                log.debug("Lock acquired")
            else:
                log.debug("Waiting to acquire lock")
                await asyncio.sleep(poll_interval)
        yield
    finally:
        if CACHE.get(CLIENTS_LOCK) == token:
            CACHE.set(CLIENTS_LOCK, None, timeout=0)
            log.debug("Lock freed")


@stats.timed("cache.read_ms")
async def blocking_read(
    req: DiscoveryRequest, timeout=CACHE_READ_TIMEOUT, poll_interval=0.05
) -> Optional[Entry]:
    id = client_id(req)
    if entry := read(id):
        return entry

    registered = False
    registration = RegisterClientRequest(request=req)
    start = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start) < timeout:
        if not registered:
            try:
                response = requests.put(WORKER_URL, json=registration.model_dump())
                if response.status_code == 200:
                    registered = True
            except Exception as e:
                stats.increment("client.registration", tags=["status:failed"])
                log.exception(f"Tried to register client but failed: {e}")
                await asyncio.sleep(1)
        if entry := read(id):
            return entry
        await asyncio.sleep(poll_interval)

    return None


def read(id: str) -> Optional[Entry]:
    if entry := CACHE.get(id):
        stats.increment("cache.hit")
        return entry
    stats.increment("cache.miss")
    return None


def write(id: str, val: Entry) -> None:
    CACHE.set(id, val)


def client_id(req: DiscoveryRequest) -> str:
    return str(req.cache_key(config.caching_rules))


def clients() -> list[tuple[str, DiscoveryRequest]]:
    return CACHE.get(CLIENTS_KEY) or []


async def register(req: DiscoveryRequest) -> tuple[str, DiscoveryRequest]:
    id = client_id(req)
    log.debug(f"Registering client {id}")
    async with lock():
        existing = clients()
        existing.append((id, req))
        CACHE.set(CLIENTS_KEY, existing)
        log.debug(f"Registered client {id}")
    return id, req


def registered(req: DiscoveryRequest) -> bool:
    item = (client_id(req), req)
    return item in clients()
