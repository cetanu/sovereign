from typing import Any
from pydantic import BaseModel
from sovereign.schemas import Node


class CacheResult(BaseModel):
    value: Any
    from_remote: bool


class Entry(BaseModel):
    text: str
    len: int
    version: str
    node: Node
