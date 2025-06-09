import asyncio
from pathlib import Path
from hashlib import blake2s
from typing import Optional

import requests
from pydantic import BaseModel
from cachelib import FileSystemCache

from sovereign import config
from sovereign.schemas import DiscoveryRequest, RegisterClientRequest


CACHE_PATH = Path("/var/run/ecp_cache")
CACHE = FileSystemCache(str(CACHE_PATH), default_timeout=0, hash_method=blake2s)


class Entry(BaseModel):
    text: str
    len: int
    version: str


async def blocking_read(
    req: DiscoveryRequest, timeout=5.0, poll_interval=0.05
) -> Optional[Entry]:
    id = client_id(req)
    if entry := read(id):
        return entry

    registration = RegisterClientRequest(request=req)
    requests.post("http://localhost:9080/register", json=registration.model_dump())

    start = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start) < timeout:
        if entry := read(id):
            return entry
        await asyncio.sleep(poll_interval)

    return None


def read(id) -> Optional[Entry]:
    return CACHE.get(id)


def write(id, val: Entry):
    CACHE.add(id, val)


def client_id(req: DiscoveryRequest):
    return str(req.cache_key(config.caching_rules))
