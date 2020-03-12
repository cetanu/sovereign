from fastapi import Body, Header
from fastapi.routing import APIRouter
from fastapi.responses import Response
from sovereign.logs import add_log_context
from sovereign import discovery, json_response_class
from sovereign.schemas import DiscoveryRequest, DiscoveryResponse
from sovereign.utils.auth import authenticate

router = APIRouter()


@router.post(
    '/discovery:{xds_type}',
    summary='Envoy Discovery Service Endpoint',
    response_model=DiscoveryResponse,
    responses={
        200: {'description': 'New resources provided'},
        304: {'description': 'Resources are up-to-date'},
        404: {'description': 'No resources found'},
    }
)
async def discovery_response(
        xds_type: discovery.DiscoveryTypes,
        discovery_request: DiscoveryRequest = Body(None),
        host: str = Header('no_host_provided'),
):
    authenticate(discovery_request)
    response: dict = await discovery.response(
        discovery_request,
        xds_type.value,
        host=host
    )
    extra_headers = {
        'X-Sovereign-Client-Build': discovery_request.envoy_version,
        'X-Sovereign-Client-Version': discovery_request.version_info,
        'X-Sovereign-Requested-Resources': ','.join(discovery_request.resource_names) or 'all',
        'X-Sovereign-Requested-Type': xds_type.value,
        'X-Sovereign-Response-Version': response['version_info']
    }
    add_log_context(
        resource_names=discovery_request.resource_names,
        envoy_ver=discovery_request.envoy_version
    )
    if response['version_info'] == discovery_request.version_info:
        # Configuration is identical, send a Not Modified response
        return Response(status_code=304, headers=extra_headers)
    elif len(response.get('resources', [])) == 0:
        return json_response_class(content={'detail': 'No resources found'}, status_code=404, headers=extra_headers)
    elif response['version_info'] != discovery_request.version_info:
        return json_response_class(content=response, headers=extra_headers)
