import logging
import os
import random
import threading
import time

from structlog.typing import FilteringBoundLogger

from sovereign import stats
from sovereign.configuration import config
from sovereign.dynamic_config import Loadable
from sovereign.v2.data.data_store import DataStoreProtocol
from sovereign.v2.data.repositories import (
    ContextRepository,
    DiscoveryEntryRepository,
    WorkerNodeRepository,
)
from sovereign.v2.data.utils import get_data_store, get_queue
from sovereign.v2.data.worker_queue import QueueProtocol
from sovereign.v2.jobs.refresh_context import get_refresh_after, refresh_context
from sovereign.v2.jobs.render_discovery_job import render_discovery_response
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
            level=logging.INFO,
        )

        self.node_id = (
            node_id
            if node_id is not None
            else f"{time.time()}{random.randint(0, 1000000)}"
        )

        data_store = data_store if data_store is not None else get_data_store()

        self.context_repository = ContextRepository(data_store)
        self.discovery_entry_repository = DiscoveryEntryRepository(data_store)
        self.worker_node_repository = WorkerNodeRepository(data_store)

        self.queue = queue if queue is not None else get_queue()

    def start(self):
        # start the context refresh loop and daemonise it
        threading.Thread(daemon=True, target=self.context_refresh_loop).start()

        # pull from the queue for eternity and process the messages
        while True:
            try:
                if message := self.queue.get():
                    job_type = type(message.job).__name__
                    stats.increment(
                        "v2.worker.queue.message_received",
                        tags=[f"job_type:{job_type}"],
                    )
                    self.process_job(message.job)
                    self.queue.ack(message.receipt_handle)
                    stats.increment(
                        "v2.worker.queue.message_acked", tags=[f"job_type:{job_type}"]
                    )
            except Exception:
                stats.increment("v2.worker.queue.error")
                self.logger.exception("Error while processing job")

    def process_job(self, job: QueueJob):
        self.logger.info(
            "Processing job from queue",
            job_type=type(job),
            job=job,
            node_id=self.node_id,
            process_id=os.getpid(),
            thread_id=threading.get_ident(),
        )

        match job:
            case RefreshContextJob():
                refresh_context(
                    job.context_name,
                    self.node_id,
                    config,
                    self.context_repository,
                    self.discovery_entry_repository,
                    self.queue,
                )
            case RenderDiscoveryJob():
                render_discovery_response(
                    job.request_hash,
                    self.context_repository,
                    self.discovery_entry_repository,
                    self.node_id,
                )

    def context_refresh_loop(self):
        self.logger.info(
            "Starting context refresh loop",
            node_id=self.node_id,
            process_id=os.getpid(),
            thread_id=threading.get_ident(),
        )

        is_leader = False

        while True:
            try:
                self.worker_node_repository.send_heartbeat(self.node_id)
                self.worker_node_repository.prune_dead_nodes()

                if not self.worker_node_repository.get_leader_node_id() == self.node_id:
                    is_leader = False
                    self.logger.info(
                        "This node is not the leader, checking again in 60 seconds",
                        node_id=self.node_id,
                        process_id=os.getpid(),
                        thread_id=threading.get_ident(),
                    )
                    time.sleep(60)
                    continue

                # I am the leader
                if not is_leader:
                    is_leader = True
                    self.logger.info(
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

                    time_now = time.time()

                    if refresh_after is None or refresh_after <= time.time():
                        job = RefreshContextJob(context_name=name)

                        self.logger.info(
                            "Queuing context refresh",
                            node_id=self.node_id,
                            process_id=os.getpid(),
                            thread_id=threading.get_ident(),
                            name=name,
                            refresh_after=refresh_after,
                            refresh_after_seconds=(refresh_after or time_now)
                            - time_now,
                        )
                        self.queue.put(job)
                        stats.increment(
                            "v2.worker.context_refresh.queued", tags=[f"context:{name}"]
                        )

                        # update refresh_after to ensure that, at most, we refresh once per interval
                        self.context_repository.update_refresh_after(
                            name, get_refresh_after(config, loadable)
                        )
                    else:
                        stats.increment(
                            "v2.worker.context_refresh.skipped",
                            tags=[f"context:{name}"],
                        )
                        self.logger.debug(
                            "Skipping context refresh",
                            node_id=self.node_id,
                            process_id=os.getpid(),
                            thread_id=threading.get_ident(),
                            name=name,
                            refresh_after=refresh_after,
                            refresh_after_seconds=(refresh_after or time_now)
                            - time_now,
                        )

                time.sleep(1)
            except Exception:
                stats.increment("v2.worker.context_refresh.error")
                self.logger.exception("Error while refreshing context")
                time.sleep(5)
