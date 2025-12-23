from typing import Any

import pydantic

from sovereign.types import DiscoveryRequest, DiscoveryResponse


class Context(pydantic.BaseModel):
    name: str
    data: Any
    data_hash: int
    refresh_after: int


class DiscoveryEntry(pydantic.BaseModel):
    request_hash: str
    template: str
    request: DiscoveryRequest
    response: DiscoveryResponse


class RefreshContextJob(pydantic.BaseModel):
    context_name: str


class RenderDiscoveryJob(pydantic.BaseModel):
    request_hash: str


QueueJob = RefreshContextJob | RenderDiscoveryJob


class WorkerNode(pydantic.BaseModel):
    id: str
    last_heartbeat: int
