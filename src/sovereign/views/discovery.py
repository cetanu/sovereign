from fastapi import Body, Header
from fastapi.routing import APIRouter
from fastapi.responses import Response
from typing import Union
from sovereign.logs import queue_log_fields
from sovereign import discovery
from sovereign.db import get_resources, put_resources, version_is_latest
from sovereign.schemas import (
    DiscoveryRequest,
    DiscoveryResponse,
    ProcessedTemplate,
    CachedTemplate,
)
from sovereign.statistics import stats
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


def response_headers(discovery_request, response, xds):
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
    xds_type: discovery.DiscoveryTypes,
    discovery_request: DiscoveryRequest = Body(...),
    host: str = Header("no_host_provided"),
):
    xds = xds_type.value
    discovery_request.desired_controlplane = host
    response = await perform_discovery(discovery_request, version, xds, skip_auth=False)
    queue_log_fields(
        XDS_RESOURCES=discovery_request.resource_names,
        XDS_ENVOY_VERSION=discovery_request.envoy_version,
        XDS_CLIENT_VERSION=discovery_request.version_info,
        XDS_SERVER_VERSION=response.version,
    )
    headers = response_headers(discovery_request, response, xds)

    if getattr(response, "resources", None) == []:
        return Response(status_code=404, headers=headers)
    if response.version == discovery_request.version_info:
        return not_modified(headers)
    elif response.version != discovery_request.version_info:
        return Response(
            response.rendered, headers=headers, media_type="application/json"
        )
    return Response(content="Resources could not be determined", status_code=500)


async def perform_discovery(
    req, api_version, xds, skip_auth=False
) -> Union[ProcessedTemplate, CachedTemplate]:
    if not skip_auth:
        authenticate(req)
    try:
        type_url = type_urls[api_version][xds]
        req.type_url = type_url
    except TypeError:
        pass

    if req.version_info != "0":  # don't use cache for initial resources
        if version_is_latest(node_id=req.uid, resource=xds, version=req.version_info):
            return ProcessedTemplate(
                resources=[], type_url=xds, version_info=req.version_info
            )

        cached_data = get_resources(
            node_id=req.uid, resource=xds, version=req.version_info
        )
        if cached_data is not None:
            stats.increment(f"discovery.{xds}.cache_hit")
            return CachedTemplate(data=cached_data)
    # Perform normal discovery and then add it to the cache
    stats.increment(f"discovery.{xds}.cache_miss")
    response = await discovery.response(req, xds)
    if isinstance(response, ProcessedTemplate):
        put_resources(
            node_id=req.uid,
            resource=xds,
            data=response.rendered,
            version=response.version,
        )
    return response


def not_modified(headers):
    return Response(status_code=304, headers=headers)
