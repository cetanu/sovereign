from asyncio import Queue, gather
from collections import defaultdict
from enum import IntEnum
from typing import Sequence, final

import pydantic

Primitives = str | int | float | bool | Sequence[str]


class Topic(IntEnum):
    CONTEXT = 1


class Event(pydantic.BaseModel):
    message: str
    metadata: dict[str, Primitives] = pydantic.Field(default_factory=dict)


@final
class EventBus:
    def __init__(self, maxsize: int = 0):
        self._topics: dict[Topic, list[Queue[Event]]] = defaultdict(list)
        self._maxsize = maxsize

    def subscribe(self, topic: Topic) -> Queue[Event]:
        q: Queue[Event] = Queue(self._maxsize)
        self._topics[topic].append(q)
        return q

    def unsubscribe(self, topic: Topic, q: Queue[Event]) -> None:
        qs = self._topics.get(topic)
        if not qs:
            return
        try:
            qs.remove(q)
        except ValueError:
            pass
        if not qs:
            _ = self._topics.pop(topic, None)

    async def publish(self, topic: Topic, msg: Event) -> None:
        qs = self._topics.get(topic, [])
        if not qs:
            return
        _ = await gather(*(q.put(msg) for q in qs))


bus = EventBus()
