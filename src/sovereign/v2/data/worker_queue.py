import logging
from queue import Empty, Queue
from typing import Protocol, runtime_checkable

from structlog.typing import FilteringBoundLogger

from sovereign.v2.logging import get_named_logger
from sovereign.v2.types import QueueJob


@runtime_checkable
class QueueProtocol(Protocol):
    def put(self, job: QueueJob) -> str | None: ...

    def get(self) -> QueueJob | None: ...


class InMemoryQueue(QueueProtocol):
    backing_queue: Queue[QueueJob]

    def __init__(self) -> None:
        self.logger: FilteringBoundLogger = get_named_logger(
            f"{self.__class__.__module__}.{self.__class__.__qualname__}",
            level=logging.DEBUG,
        )

        self.backing_queue = Queue()

    def put(self, job: QueueJob) -> str | None:
        self.logger.debug(
            "Putting job in queue",
            job=job,
            queue_size_before=self.backing_queue.qsize(),
        )
        self.backing_queue.put(job)

    def get(self) -> QueueJob | None:
        try:
            return self.backing_queue.get(True, timeout=30)
        except Empty:
            return None

    def is_empty(self) -> bool:
        return self.backing_queue.empty()
