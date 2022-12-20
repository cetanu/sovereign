from os import getenv
from typing import Dict

from fastapi import Body, Header
from fastapi.routing import APIRouter
from fastapi.responses import Response

from sovereign import discovery, logs
from sovereign.utils.auth import authenticate
from sovereign.utils.version_info import compute_hash
from sovereign.schemas import (
    DiscoveryRequest,
    DiscoveryResponse,
    ProcessedTemplate,
)


if cache_discovery_enabled := getenv(
    "SOVEREIGN_DISCOVERY_CACHE_ENABLED", "false"
).lower() in ("true", "1", "t"):
    cache_redis_host = getenv("SOVEREIGN_DISCOVERY_CACHE_REDIS_HOST", "localhost")
    cache_redis_port = getenv("SOVEREIGN_DISCOVERY_CACHE_REDIS_PORT", 6379)
    if getenv("SOVEREIGN_DISCOVERY_CACHE_REDIS_SECURE", "false").lower() in (
        "true",
        "1",
        "t",
    ):
        cache_redis_protocol = "rediss://"
    else:
        cache_redis_protocol = "redis://"
    from cashews import cache

    cache.setup(
        f"{cache_redis_protocol}{cache_redis_host}:{cache_redis_port}",
        password=getenv("SOVEREIGN_DISCOVERY_CACHE_REDIS_PASSWORD", None),
        client_side=True,  # True = Try in-memory cache before hitting redis
        wait_for_connection_timeout=2,
        socket_connect_timeout=2,
        socket_timeout=2,
        max_connections=10,  # Default = 10
        retry_on_timeout=True,  # Retry connections if they timeout.
        safe=False,  # False = Don't supress connection errors. True = Supress connection errors
        socket_keepalive=True,  # Try to keep connections to redis around.
        enable=True,
    )

router = APIRouter()

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


def response_headers(
    discovery_request: DiscoveryRequest, response: ProcessedTemplate, xds: str
) -> Dict[str, str]:
    return {
        "X-Sovereign-Client-Build": discovery_request.envoy_version,
        "X-Sovereign-Client-Version": discovery_request.version_info,
        "X-Sovereign-Requested-Resources": ",".join(discovery_request.resource_names)
        or "all",
        "X-Sovereign-Requested-Type": xds,
        "X-Sovereign-Response-Version": response.version,
    }


@router.post(
    "/{version}/discovery:{xds_type}",
    summary="Envoy Discovery Service Endpoint",
    response_model=DiscoveryResponse,
    responses={
        200: {"description": "New resources provided"},
        304: {"description": "Resources are up-to-date"},
        404: {"description": "No resources found"},
    },
)
async def discovery_response(
    version: str,
    xds_type: str,
    discovery_request: DiscoveryRequest = Body(...),
    host: str = Header("no_host_provided"),
) -> Response:
    discovery_request.desired_controlplane = host
    response = await perform_discovery(
        discovery_request, version, xds_type, skip_auth=False
    )
    logs.queue_log_fields(
        XDS_RESOURCES=discovery_request.resource_names,
        XDS_ENVOY_VERSION=discovery_request.envoy_version,
        XDS_CLIENT_VERSION=discovery_request.version_info,
        XDS_SERVER_VERSION=response.version,
    )
    if discovery_request.error_detail:
        logs.queue_log_fields(XDS_ERROR_DETAIL=discovery_request.error_detail.message)
    headers = response_headers(discovery_request, response, xds_type)

    if response.version == discovery_request.version_info:
        return not_modified(headers)
    elif getattr(response, "resources", None) == []:
        return Response(status_code=404, headers=headers)
    elif response.version != discovery_request.version_info:
        return Response(
            response.rendered, headers=headers, media_type="application/json"
        )
    return Response(content="Resources could not be determined", status_code=500)


async def perform_discovery(
    req: DiscoveryRequest,
    api_version: str,
    resource_type: str,
    skip_auth: bool = False,
) -> ProcessedTemplate:
    if not skip_auth:
        authenticate(req)
    if cache_discovery_enabled:
        logs.queue_log_fields(CACHE_XDS_HIT=False)
        cache_key = compute_hash(
            [
                api_version,
                resource_type,
                req.envoy_version,
                req.resource_names,
                req.desired_controlplane,
                req.hide_private_keys,
                req.type_url,
                req.node.cluster,
                req.node.locality,
                req.node.metadata.get("auth", None),
                req.node.metadata.get("num_cpus", None),
            ]
        )
        if template := await cache.get(key=cache_key, default=None):
            logs.queue_log_fields(CACHE_XDS_HIT=True)
            return template  # type: ignore[no-any-return]
    template = discovery.response(req, resource_type)
    type_url = type_urls.get(api_version, {}).get(resource_type)
    if type_url is not None:
        for resource in template.resources:
            if not resource.get("@type"):
                resource["@type"] = type_url
    if cache_discovery_enabled:
        await cache.set(
            key=cache_key,
            value=template,
            expire=getenv("SOVEREIGN_DISCOVERY_CACHE_TTL", 60),
        )
    return template  # type: ignore[no-any-return]


def not_modified(headers: Dict[str, str]) -> Response:
    return Response(status_code=304, headers=headers)
