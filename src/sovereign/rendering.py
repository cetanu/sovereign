"""
Discovery
---------

Functions used to render and return discovery responses to Envoy proxies.

The templates are configurable. `todo See ref:Configuration#Templates`
"""

from typing import Any, Dict, List

import yaml
import pydantic
from starlette.exceptions import HTTPException
from yaml.parser import ParserError, ScannerError  # type: ignore

try:
    import sentry_sdk

    SENTRY_INSTALLED = True
except ImportError:
    SENTRY_INSTALLED = False

from sovereign import config, logs, cache, stats
from sovereign.schemas import (
    DiscoveryRequest,
    ProcessedTemplate,
)


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


def generate(job: RenderJob) -> None:
    request = job.request
    tags = [f"type:{request.resource_type}"]
    stats.increment("template.render", tags=tags)
    with stats.timed("template.render_ms", tags=tags):
        content = request.template(
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
        cache.write(
            job.id,
            cache.Entry(
                text=response.model_dump_json(indent=None),
                len=len(response.resources),
                version=response.version_info,
                node=request.node,
            ),
        )


def batch_generate(jobs: list[RenderJob]) -> None:
    for job in jobs:
        generate(job)


def deserialize_config(content: str) -> Dict[str, Any]:
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

        if SENTRY_INSTALLED and config.sentry_dsn:
            sentry_sdk.capture_exception(e)

        raise HTTPException(
            status_code=500,
            detail="Failed to load configuration, there may be "
            "a syntax error in the configured templates. "
            "Please check Sentry if you have configured Sentry DSN",
        )
    if not isinstance(envoy_configuration, dict):
        raise RuntimeError(
            f"Deserialized configuration is of unexpected format: {envoy_configuration}"
        )
    return envoy_configuration


def filter_resources(
    generated: List[Dict[str, Any]], requested: List[str]
) -> List[Dict[str, Any]]:
    """
    If Envoy specifically requested a resource, this removes everything
    that does not match the name of the resource.
    If Envoy did not specifically request anything, every resource is retained.
    """
    if len(requested) == 0:
        return generated
    return [resource for resource in generated if resource_name(resource) in requested]


def resource_name(resource: Dict[str, Any]) -> str:
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
