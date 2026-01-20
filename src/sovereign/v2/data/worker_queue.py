import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from structlog.typing import FilteringBoundLogger

from sovereign import config
from sovereign.v2.logging import get_named_logger
from sovereign.v2.types import QueueJob, queue_job_type_adapter

if config.worker_v2_queue_invsibility_time is None:
    DEFAULT_VISIBILITY_TIMEOUT_SECONDS = int(config.cache.read_timeout) + 30
else:
    DEFAULT_VISIBILITY_TIMEOUT_SECONDS = config.worker_v2_queue_invsibility_time


@dataclass
class QueueMessage:
    """A message retrieved from the queue, containing the job and a receipt handle for acknowledgement."""

    job: QueueJob
    receipt_handle: str


@runtime_checkable
class QueueProtocol(Protocol):
    def put(self, job: QueueJob) -> str | None: ...

    def get(self) -> QueueMessage | None: ...

    def ack(self, receipt_handle: str) -> bool: ...


class InMemoryQueue(QueueProtocol):
    """
    Messages become invisible when retrieved and must be acknowledged within the
    visibility timeout, otherwise they become visible again for other workers.
    """

    def __init__(
        self, visibility_timeout: int | None = DEFAULT_VISIBILITY_TIMEOUT_SECONDS
    ) -> None:
        self.logger: FilteringBoundLogger = get_named_logger(
            f"{self.__class__.__module__}.{self.__class__.__qualname__}",
            level=logging.INFO,
        )

        self.visibility_timeout: int = (
            visibility_timeout
            if visibility_timeout is not None
            else DEFAULT_VISIBILITY_TIMEOUT_SECONDS
        )

        # storage for messages: message_id -> (job, invisible_until, receipt_handle)
        self._messages: dict[str, tuple[QueueJob, float | None, str | None]] = {}

    def put(self, job: QueueJob) -> str | None:
        message_id = str(uuid.uuid4())
        self._messages[message_id] = (job, None, None)  # visible, no receipt handle
        self.logger.debug(
            "Putting job in queue",
            job=job,
            message_id=message_id,
            queue_size=len(self._messages),
        )
        return message_id

    def get(self) -> QueueMessage | None:
        timeout = 30
        start_time = int(time.time())
        poll_interval_seconds = 0.5

        while int(time.time()) - start_time < timeout:
            now = int(time.time())
            # find first visible message (not invisible, or invisibility expired)
            for message_id, (job, invisible_until, _) in self._messages.items():
                # check if message is visible
                if invisible_until is None or invisible_until <= now:
                    # make it invisible and generate new receipt handle
                    receipt_handle = str(uuid.uuid4())
                    new_invisible_until = now + self.visibility_timeout
                    self._messages[message_id] = (
                        job,
                        new_invisible_until,
                        receipt_handle,
                    )

                    self.logger.debug(
                        "Retrieved job from queue",
                        message_id=message_id,
                        receipt_handle=receipt_handle,
                        invisible_until=new_invisible_until,
                    )
                    return QueueMessage(job=job, receipt_handle=receipt_handle)

            time.sleep(poll_interval_seconds)

        return None

    def ack(self, receipt_handle: str) -> bool:
        """
        Acknowledge a message, permanently removing it from the queue.

        Returns True if the message was successfully acknowledged, False if the
        receipt handle was invalid (message doesn't exist or was redelivered).
        """
        for message_id, (job, invisible_until, stored_receipt) in list(
            self._messages.items()
        ):
            if stored_receipt == receipt_handle:
                del self._messages[message_id]
                self.logger.debug(
                    "Acknowledged job",
                    message_id=message_id,
                    receipt_handle=receipt_handle,
                )
                return True

        self.logger.warning(
            "Failed to acknowledge job, invalid receipt handle",
            receipt_handle=receipt_handle,
        )
        return False

    def is_empty(self) -> bool:
        return not self._messages


class SqliteQueue(QueueProtocol):
    """
    SQLite-backed queue with visibility timeout support.

    Messages become invisible when retrieved and must be acknowledged within the
    visibility timeout, otherwise they become visible again for other workers.
    """

    def __init__(self, visibility_timeout: int = DEFAULT_VISIBILITY_TIMEOUT_SECONDS):
        self.logger: FilteringBoundLogger = get_named_logger(
            f"{self.__class__.__module__}.{self.__class__.__qualname__}",
            level=logging.INFO,
        )
        self.visibility_timeout = visibility_timeout
        self.db_path = config.worker_v2_queue_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        # check_same_thread=False allows SQLite connections to be shared across threads
        # and means that we need to ensure thread safety ourselves.
        # isolation_level=None uses autocommit mode,
        # which prevents "cannot commit - no transaction is active" errors in multi-threaded contexts.
        conn = sqlite3.connect(
            self.db_path, check_same_thread=False, isolation_level=None
        )
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        try:
            with self._get_connection() as conn:
                conn.execute("""
                             CREATE TABLE IF NOT EXISTS queue
                             (
                                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                                 data TEXT NOT NULL,
                                 invisible_until INT,
                                 receipt_handle TEXT
                             )
                             """)
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_invisible_until ON queue (invisible_until)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_receipt_handle ON queue (receipt_handle)"
                )
                conn.commit()
        except Exception:
            self.logger.exception("Failed to initialise SQLite queue database")
            raise

    def put(self, job: QueueJob) -> str | None:
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "INSERT INTO queue (data, invisible_until, receipt_handle) VALUES (?, NULL, NULL)",
                    (job.model_dump_json(),),
                )
                job_id = str(cursor.lastrowid)
                self.logger.debug("Put job in SQLite queue", job=job, job_id=job_id)
                return str(job_id)
        except Exception:
            self.logger.exception("Failed to put job in SQLite queue", job=job)
            return None

    def get(self) -> QueueMessage | None:
        timeout = 30
        start_time = time.time()
        poll_interval_seconds = 0.5

        while time.time() - start_time < timeout:
            try:
                with self._get_connection() as conn:
                    now = int(time.time())
                    # find first visible message (invisible_until is NULL or expired)
                    cursor = conn.execute(
                        """
                        SELECT id, data
                        FROM queue
                        WHERE invisible_until IS NULL
                           OR invisible_until <= ? LIMIT 1
                        """,
                        (now,),
                    )
                    row = cursor.fetchone()
                    if row:
                        # generate receipt handle and make message invisible
                        receipt_handle = str(uuid.uuid4())
                        invisible_until = now + self.visibility_timeout
                        conn.execute(
                            "UPDATE queue SET invisible_until = ?, receipt_handle = ? WHERE id = ?",
                            (invisible_until, receipt_handle, row["id"]),
                        )
                        conn.commit()
                        self.logger.debug(
                            "Retrieved job from queue",
                            job_id=row["id"],
                            receipt_handle=receipt_handle,
                            invisible_until=invisible_until,
                        )
                        job = queue_job_type_adapter.validate_json(row["data"])
                        return QueueMessage(job=job, receipt_handle=receipt_handle)
            except Exception:
                self.logger.exception("Failed to get job from SQLite queue")
                return None

            time.sleep(poll_interval_seconds)

        return None

    def ack(self, receipt_handle: str) -> bool:
        """
        Acknowledge a message, permanently removing it from the queue.

        Returns True if the message was successfully acknowledged, False if the
        receipt handle was invalid (message doesn't exist or was redelivered).
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "DELETE FROM queue WHERE receipt_handle = ?",
                    (receipt_handle,),
                )
                conn.commit()
                if cursor.rowcount > 0:
                    self.logger.debug(
                        "Acknowledged job",
                        receipt_handle=receipt_handle,
                    )
                    return True
                else:
                    self.logger.warning(
                        "Failed to acknowledge job, invalid receipt handle",
                        receipt_handle=receipt_handle,
                    )
                    return False
        except Exception:
            self.logger.exception(
                "Failed to acknowledge job in SQLite queue",
                receipt_handle=receipt_handle,
            )
            return False
