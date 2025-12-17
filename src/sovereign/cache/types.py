from typing import Any

from pydantic import BaseModel

from sovereign.types import Node


class CacheResult(BaseModel):
    value: Any
    from_remote: bool


class Entry(BaseModel):
    text: str
    len: int
    version: str
    node: Node
