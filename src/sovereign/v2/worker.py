import logging
import os
import random
import threading
import time

from structlog.typing import FilteringBoundLogger

from sovereign.configuration import config
from sovereign.dynamic_config import Loadable
from sovereign.utils.entry_point_loader import EntryPointLoader
from sovereign.v2.data.data_store import DataStoreProtocol
from sovereign.v2.data.repositories import (
    ContextRepository,
    DiscoveryEntryRepository,
    WorkerNodeRepository,
)
from sovereign.v2.data.worker_queue import QueueProtocol
from sovereign.v2.jobs.refresh_context import get_refresh_after, refresh_context
from sovereign.v2.logging import get_named_logger
from sovereign.v2.types import (
    QueueJob,
    RefreshContextJob,
    RenderDiscoveryJob,
)


class Worker:
    context_repository: ContextRepository
    discovery_entry_repository: DiscoveryEntryRepository
    worker_node_repository: WorkerNodeRepository

    queue: QueueProtocol

    def __init__(
        self,
        data_store: DataStoreProtocol | None = None,
        node_id: str | None = None,
        queue: QueueProtocol | None = None,
    ) -> None:
        self.logger: FilteringBoundLogger = get_named_logger(
            f"{self.__class__.__module__}.{self.__class__.__qualname__}",
            level=logging.DEBUG,
        )

        self.node_id = (
            node_id
            if node_id is not None
            else f"{time.time()}{random.randint(0, 1000000)}"
        )

        data_store = data_store if data_store is not None else self._get_data_store()

        self.context_repository = ContextRepository(data_store)
        self.discovery_entry_repository = DiscoveryEntryRepository(data_store)
        self.worker_node_repository = WorkerNodeRepository(data_store)

        self.queue = queue if queue is not None else self._get_queue()

    @staticmethod
    def _get_data_store() -> DataStoreProtocol:
        entry_points = EntryPointLoader("data_stores")
        data_store: DataStoreProtocol | None = None

        for entry_point in entry_points.groups["data_stores"]:
            if entry_point.name == config.worker_v2_data_store_provider:
                data_store = entry_point.load()()
                break

        if data_store is None:
            raise ValueError(
                f"Data store '{config.worker_v2_data_store_provider}' not found in entry points"
            )

        return data_store

    @staticmethod
    def _get_queue() -> QueueProtocol:
        entry_points = EntryPointLoader("queues")

        for entry_point in entry_points.groups["queues"]:
            if entry_point.name == config.worker_v2_queue_provider:
                return entry_point.load()()

        raise ValueError(
            f"Queue '{config.worker_v2_queue_provider}' not found in entry points"
        )

    def start(self):
        # start the context refresh loop and daemonise it
        threading.Thread(daemon=True, target=self.context_refresh_loop).start()

        # pull from the queue for eternity and process the messages
        while True:
            if job := self.queue.get():
                self.process_job(job)

    def process_job(self, job: QueueJob):
        match job:
            case RefreshContextJob():
                refresh_context(
                    job.context_name,
                    config,
                    self.context_repository,
                    self.discovery_entry_repository,
                    self.queue,
                )
            case RenderDiscoveryJob():
                # todo:
                # render_discovery_response(
                #     self.context_repository, self.discovery_job_repository, job
                # )
                pass

    def context_refresh_loop(self):
        self.logger.info(
            "Starting context refresh loop",
            node_id=self.node_id,
            process_id=os.getpid(),
            thread_id=threading.get_ident(),
        )

        while True:
            try:
                self.worker_node_repository.send_heartbeat(self.node_id)
                self.worker_node_repository.prune_dead_nodes()

                if not self.worker_node_repository.get_leader_node_id() == self.node_id:
                    self.logger.debug(
                        "This node is not the leader, checking again in 60 seconds",
                        node_id=self.node_id,
                        process_id=os.getpid(),
                        thread_id=threading.get_ident(),
                    )
                    time.sleep(60)
                    continue

                # I am the leader
                self.logger.debug(
                    "This node is the leader, begin refreshing contexts",
                    node_id=self.node_id,
                    process_id=os.getpid(),
                    thread_id=threading.get_ident(),
                )
                name: str
                loadable: Loadable
                for name, loadable in config.template_context.context.items():
                    refresh_after: int | None = (
                        self.context_repository.get_refresh_after(name)
                    )
                    status = "SKIPPED"

                    if refresh_after is None or refresh_after <= time.time():
                        status = "QUEUED"
                        job = RefreshContextJob(context_name=name)
                        self.queue.put(job)

                        # update refresh_after to ensure that, at most, we refresh once per interval
                        self.context_repository.update_refresh_after(
                            name, get_refresh_after(config, loadable)
                        )

                    time_now = time.time()
                    self.logger.debug(
                        "Initiating context refresh",
                        node_id=self.node_id,
                        process_id=os.getpid(),
                        thread_id=threading.get_ident(),
                        context_name=name,
                        context_status=status,
                        context_refresh_after=refresh_after,
                        context_refresh_after_seconds=(refresh_after or time_now)
                        - time_now,
                    )
                time.sleep(1)
            except Exception:
                self.logger.exception("Error while refreshing context")
                time.sleep(5)
