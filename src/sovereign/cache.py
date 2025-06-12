import asyncio
from pathlib import Path
from hashlib import blake2s
from typing import Optional

import requests
from pydantic import BaseModel
from cachelib import FileSystemCache, RedisCache

from sovereign import config, application_logger as log
from sovereign.schemas import DiscoveryRequest, Node, RegisterClientRequest


CACHE_READ_TIMEOUT = config.cache_timeout
CACHE_PATH = Path(config.cache_path)
CACHE = FileSystemCache(str(CACHE_PATH), default_timeout=0, hash_method=blake2s)

redis = config.discovery_cache
if redis.enabled:
    CACHE = RedisCache(
        host=redis.host,
        port=redis.port,
        password=redis.password.get_secret_value(),
        key_prefix="discovery_request_",
        default_timeout=300,
    )


class Entry(BaseModel):
    text: str
    len: int
    version: str
    node: Node


async def blocking_read(
    req: DiscoveryRequest, timeout=CACHE_READ_TIMEOUT, poll_interval=0.05
) -> Optional[Entry]:
    id = client_id(req)
    if entry := read(id):
        return entry

    registration = RegisterClientRequest(request=req)
    try:
        requests.put("http://localhost:9080/client", json=registration.model_dump())
    except Exception as e:
        log.exception(f"Tried to register client but failed: {e}")

    start = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start) < timeout:
        if entry := read(id):
            return entry
        await asyncio.sleep(poll_interval)

    return None


def read(id: str) -> Optional[Entry]:
    return CACHE.get(id)


def write(id: str, val: Entry) -> None:
    CACHE.set(id, val)


def client_id(req: DiscoveryRequest) -> str:
    return str(req.cache_key(config.caching_rules))
