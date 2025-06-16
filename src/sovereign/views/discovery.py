from fastapi import Body, Header
from fastapi.responses import Response
from fastapi.routing import APIRouter

from sovereign import cache, logs
from sovereign.utils.auth import authenticate
from sovereign.schemas import (
    DiscoveryRequest,
    DiscoveryResponse,
)


def not_modified() -> Response:
    return Response(status_code=304)


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

    def handle_response(entry: cache.Entry):
        logs.access_logger.queue_log_fields(
            XDS_RESOURCES=xds_req.resource_names,
            XDS_ENVOY_VERSION=xds_req.envoy_version,
            XDS_CLIENT_VERSION=xds_req.version_info,
            XDS_SERVER_VERSION=entry.version,
        )
        if entry.len == 0:
            return Response(status_code=404)
        if entry.version == xds_req.version_info:
            return not_modified()
        return Response(entry.text, media_type="application/json")

    if entry := await cache.blocking_read(xds_req):
        return handle_response(entry)

    return Response(content="Something went wrong", status_code=500)
