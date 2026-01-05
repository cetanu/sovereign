from fastapi import Body, Header
from fastapi.responses import Response
from fastapi.routing import APIRouter

from sovereign import cache, config, logs
from sovereign.cache.types import Entry
from sovereign.types import (
    DiscoveryRequest,
    DiscoveryResponse,
)
from sovereign.utils.auth import authenticate
from sovereign.v2.web import wait_for_discovery_response
from sovereign.views import reader


def response_headers(
    discovery_request: DiscoveryRequest, response: Entry, xds: str
) -> dict[str, str]:
    return {
        "X-Sovereign-Client-Build": discovery_request.envoy_version,
        "X-Sovereign-Client-Version": discovery_request.version_info,
        "X-Sovereign-Requested-Resources": ",".join(discovery_request.resource_names)
        or "all",
        "X-Sovereign-Requested-Type": xds,
        "X-Sovereign-Response-Version": response.version,
    }


router = APIRouter()


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
    xds_req: DiscoveryRequest = Body(...),
    host: str = Header("no_host_provided"),
) -> Response:
    authenticate(xds_req)

    # Pack additional info into the request
    xds_req.desired_controlplane = host
    xds_req.resource_type = xds_type
    xds_req.api_version = version
    if xds_req.error_detail:
        logs.access_logger.queue_log_fields(
            XDS_ERROR_DETAIL=xds_req.error_detail.message
        )
    logs.access_logger.queue_log_fields(
        XDS_RESOURCES=xds_req.resource_names,
        XDS_ENVOY_VERSION=xds_req.envoy_version,
        XDS_CLIENT_VERSION=xds_req.version_info,
    )

    def handle_response(entry: cache.Entry):
        logs.access_logger.queue_log_fields(
            XDS_SERVER_VERSION=entry.version,
        )
        headers = response_headers(xds_req, entry, xds_type)
        if entry.len == 0:
            return Response(status_code=404, headers=headers)
        if entry.version == xds_req.version_info:
            return Response(status_code=304, headers=headers)
        return Response(entry.text, media_type="application/json", headers=headers)

    if config.worker_v2_enabled:
        # we're set up to use v2 of the worker
        response = await wait_for_discovery_response(xds_req)
        if response is not None:
            entry = Entry(
                text=response.model_dump_json(indent=None),
                len=len(response.resources),
                version=response.version_info,
                node=xds_req.node,
            )
            return handle_response(entry)

    else:
        entry: Entry | None
        if entry := await reader.blocking_read(xds_req):  # ty: ignore[possibly-missing-attribute]
            return handle_response(entry)

    return Response(content="Something went wrong", status_code=500)
