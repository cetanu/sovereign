import schedule
from fastapi import Body, BackgroundTasks
from fastapi.routing import APIRouter
from sovereign.logs import add_log_context
from starlette.responses import UJSONResponse, Response
from sovereign import discovery
from sovereign.statistics import stats
from sovereign.schemas import DiscoveryRequest, DiscoveryResponse
from sovereign.utils.auth import authenticate

router = APIRouter()


@router.post(
    '/discovery:{xds_type}',
    summary='Envoy Discovery Service Endpoint',
    response_model=DiscoveryResponse,
    responses={
        200: {
            'description': 'New resources provided'
        },
        304: {
            'description': 'Resources are up-to-date'
        }
    }
)
async def discovery_response(
        xds_type: discovery.DiscoveryTypes,
        background_tasks: BackgroundTasks,
        discovery_request: DiscoveryRequest = Body(None)
):
    background_tasks.add_task(schedule.run_pending)

    authenticate(discovery_request)
    response: dict = await discovery.response(discovery_request, xds_type.value)

    add_log_context(
        resource_names=discovery_request.resource_names,
        envoy_ver=discovery_request.envoy_version
    )

    if response['version_info'] == discovery_request.version_info:
        ret = 'No changes'
        code = 304
    elif len(response.get('resources', [])) == 0:
        ret = 'No resources found'
        code = 404
    elif response['version_info'] != discovery_request.version_info:
        ret = response
        code = 200
    else:
        ret = 'Unknown Error'
        code = 500

    metrics_tags = [
        f"client_version:{discovery_request.envoy_version}",
        f"response_code:{code}",
        f"xds_type:{xds_type.value}"
    ]
    metrics_tags += [f"resource:{resource}" for resource in discovery_request.resource_names]
    stats.increment('discovery.rq_total', tags=metrics_tags)

    if code == 304:
        # A 304 response cannot contain a message-body; it is always terminated
        # by the first empty line after the header fields.
        return Response(status_code=code)
    else:
        return UJSONResponse(content=ret, status_code=code)
