"""
Discovery
---------

Functions used to render and return discovery responses to Envoy proxies.

The templates are configurable. `todo See ref:Configuration#Templates`
"""

import importlib
import os
import traceback
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pipe, Process, cpu_count

# noinspection PyProtectedMember
from multiprocessing.connection import Connection
from typing import Any

import pydantic

from sovereign import application_logger as log
from sovereign import cache, stats
from sovereign.cache.types import Entry
from sovereign.configuration import config
from sovereign.rendering_common import (
    add_type_urls,
    deserialize_config,
    filter_resources,
)
from sovereign.types import DiscoveryRequest, ProcessedTemplate
from sovereign.utils import templates

writer = cache.CacheWriter()
# limit render jobs to number of cores
POOL = ThreadPoolExecutor(max_workers=cpu_count())


class RenderJob(pydantic.BaseModel):
    id: str
    request: DiscoveryRequest
    context: dict[str, Any]

    def submit(self):
        return POOL.submit(self._run)

    def _run(self):
        rx, tx = Pipe()
        proc = Process(target=generate, args=[self, tx])
        proc.start()
        log.info(
            (
                f"Spawning process for id={self.id} "
                f"max_workers={POOL._max_workers} "
                f"threads={len(POOL._threads)} "
                f"shutdown={POOL._shutdown} "
                f"queue_size={POOL._work_queue.qsize()}"
            )
        )
        proc.join(timeout=60)  # TODO: render timeout configurable
        if proc.is_alive():
            log.warning(f"Render job for {self.id} has been running longer than 60s")
        while rx.poll(timeout=10):
            level, message = rx.recv()
            logger = getattr(log, level)
            logger(message)


# noinspection DuplicatedCode
def generate(job: RenderJob, tx: Connection) -> None:
    request = job.request
    tags = [f"type:{request.resource_type}"]
    try:
        with stats.timed("template.render_ms", tags=tags):
            content = request.template.generate(
                discovery_request=request,
                host_header=request.desired_controlplane,
                resource_names=request.resources,
                utils=templates,
                **job.context,
            )
            if not request.template.is_python_source:
                assert isinstance(content, str)
                content = deserialize_config(content)
            assert isinstance(content, dict)
            resources = filter_resources(content["resources"], request.resources)
            add_type_urls(request.api_version, request.resource_type, resources)
            response = ProcessedTemplate(resources=resources)
            tx.send(
                (
                    "info",
                    f"Completed rendering of {request}: client_id={job.id} version={response.version_info} "
                    f"resources={len(response.resources)} pid={os.getpid()}",
                )
            )
            cached, cache_result = writer.set(
                job.id,
                Entry(
                    text=response.model_dump_json(indent=None),
                    len=len(response.resources),
                    version=response.version_info,
                    node=request.node,
                ),
            )
            tx.send(cache_result)
            if cached:
                tags.append("result:ok")
            else:
                tags.append("result:cache_failed")
    except Exception as e:
        tx.send(
            (
                "error",
                f"Failed to render job for {job.id}: " + str(traceback.format_exc()),
            )
        )
        tags.append("result:err")
        tags.append(f"error:{e.__class__.__name__.lower()}")
        if config.sentry_dsn.get_secret_value():
            mod = importlib.import_module("sentry_sdk")
            mod.capture_exception(e)
    finally:
        stats.increment("template.render", tags=tags)
        tx.close()
