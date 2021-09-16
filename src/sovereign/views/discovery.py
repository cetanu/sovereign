from typing import Dict
from fastapi import Body, Header
from fastapi.routing import APIRouter
from fastapi.responses import Response
from sovereign import discovery, logs
from sovereign.schemas import (
    DiscoveryRequest,
    DiscoveryResponse,
    ProcessedTemplate,
)
from sovereign.utils.auth import authenticate

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
    },
}


def response_headers(
    discovery_request: DiscoveryRequest,
    response: ProcessedTemplate,
    xds: discovery.DiscoveryTypes,
) -> Dict[str, str]:
    return {
        "X-Sovereign-Client-Build": discovery_request.envoy_version,
        "X-Sovereign-Client-Version": discovery_request.version_info,
        "X-Sovereign-Requested-Resources": ",".join(discovery_request.resource_names)
        or "all",
        "X-Sovereign-Requested-Type": xds.value,
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
    xds_type: discovery.DiscoveryTypes,
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
    xds: discovery.DiscoveryTypes,
    skip_auth: bool = False,
) -> ProcessedTemplate:
    if not skip_auth:
        authenticate(req)
    try:
        type_url = type_urls[api_version][xds.value]
        req.type_url = type_url
    except TypeError:
        pass
    response = await discovery.response(req, xds)
    return response


def not_modified(headers: Dict[str, str]) -> Response:
    return Response(status_code=304, headers=headers)
