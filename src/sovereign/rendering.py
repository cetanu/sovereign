"""
Discovery
---------

Functions used to render and return discovery responses to Envoy proxies.

The templates are configurable. `todo See ref:Configuration#Templates`
"""

import importlib
import traceback
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pipe, Process, cpu_count
from multiprocessing.connection import Connection
from typing import Any

import pydantic
import yaml
from starlette.exceptions import HTTPException
from yaml.parser import ParserError, ScannerError  # type: ignore

from sovereign import application_logger as log
from sovereign import cache, logs, stats
from sovereign.cache.types import Entry
from sovereign.configuration import config
from sovereign.types import DiscoveryRequest, ProcessedTemplate

writer = cache.CacheWriter()
# limit render jobs to number of cores
POOL = ThreadPoolExecutor(max_workers=cpu_count())

type_urls = {
    "v2": {
        "listeners": "type.googleapis.com/envoy.api.v2.Listener",
        "clusters": "type.googleapis.com/envoy.api.v2.Cluster",
        "endpoints": "type.googleapis.com/envoy.api.v2.ClusterLoadAssignment",
        "secrets": "type.googleapis.com/envoy.api.v2.auth.Secret",
        "routes": "type.googleapis.com/envoy.api.v2.RouteConfiguration",
        "scoped-routes": "type.googleapis.com/envoy.api.v2.ScopedRouteConfiguration",
    },
    "v3": {
        "listeners": "type.googleapis.com/envoy.config.listener.v3.Listener",
        "clusters": "type.googleapis.com/envoy.config.cluster.v3.Cluster",
        "endpoints": "type.googleapis.com/envoy.config.endpoint.v3.ClusterLoadAssignment",
        "secrets": "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.Secret",
        "routes": "type.googleapis.com/envoy.config.route.v3.RouteConfiguration",
        "scoped-routes": "type.googleapis.com/envoy.config.route.v3.ScopedRouteConfiguration",
        "runtime": "type.googleapis.com/envoy.service.runtime.v3.Runtime",
    },
}


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


def generate(job: RenderJob, tx: Connection) -> None:
    request = job.request
    tags = [f"type:{request.resource_type}"]
    try:
        with stats.timed("template.render_ms", tags=tags):
            content = request.template.generate(
                discovery_request=request,
                host_header=request.desired_controlplane,
                resource_names=request.resources,
                **job.context,
            )
            if not request.template.is_python_source:
                assert isinstance(content, str)
                content = deserialize_config(content)
            assert isinstance(content, dict)
            resources = filter_resources(content["resources"], request.resources)
            add_type_urls(request.api_version, request.resource_type, resources)
            response = ProcessedTemplate(resources=resources)
            tx.send(("info", f"Completed rendering of {request} for {job.id}"))
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


def deserialize_config(content: str) -> dict[str, Any]:
    try:
        envoy_configuration = yaml.safe_load(content)
    except (ParserError, ScannerError) as e:
        logs.access_logger.queue_log_fields(
            error=repr(e),
            YAML_CONTEXT=e.context,
            YAML_CONTEXT_MARK=e.context_mark,
            YAML_NOTE=e.note,
            YAML_PROBLEM=e.problem,
            YAML_PROBLEM_MARK=e.problem_mark,
        )

        if config.sentry_dsn:
            mod = importlib.import_module("sentry_sdk")
            mod.capture_exception(e)

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to load configuration, there may be "
                "a syntax error in the configured templates. "
                "Please check Sentry if you have configured Sentry DSN"
            ),
        )
    if not isinstance(envoy_configuration, dict):
        raise RuntimeError(
            f"Deserialized configuration is of unexpected format: {envoy_configuration}"
        )
    return envoy_configuration


def filter_resources(
    generated: list[dict[str, Any]], requested: list[str]
) -> list[dict[str, Any]]:
    """
    If Envoy specifically requested a resource, this removes everything
    that does not match the name of the resource.
    If Envoy did not specifically request anything, every resource is retained.
    """
    if len(requested) == 0:
        return generated
    return [resource for resource in generated if resource_name(resource) in requested]


def resource_name(resource: dict[str, Any]) -> str:
    name = resource.get("name") or resource.get("cluster_name")
    if isinstance(name, str):
        return name
    raise KeyError(
        f"Failed to determine the name or cluster_name of the following resource: {resource}"
    )


def add_type_urls(api_version, resource_type, resources):
    type_url = type_urls.get(api_version, {}).get(resource_type)
    if type_url is not None:
        for resource in resources:
            if not resource.get("@type"):
                resource["@type"] = type_url
