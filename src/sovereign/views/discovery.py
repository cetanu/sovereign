import schedule
from fastapi import Body, BackgroundTasks
from fastapi.routing import APIRouter
from sovereign.logs import add_log_context
from starlette.responses import UJSONResponse
from sovereign import discovery, config
from sovereign.statistics import stats
from sovereign.schemas import DiscoveryRequest, DiscoveryResponse
from sovereign.utils.auth import authenticate

router = APIRouter()


@router.post(
    '/discovery:{xds_type}',
    summary='Envoy Discovery Service Endpoint',
    responses={
        200: {
            'model': DiscoveryResponse,
            'description': 'New resources provided'
        },
        config.no_changes_response_code: {
            'description': 'Resources are up-to-date'
        }
    }
)
async def discovery_response(
        xds_type: discovery.DiscoveryTypes,
        background_tasks: BackgroundTasks,
        discovery_request: DiscoveryRequest = Body(None)
):
    authenticate(discovery_request)
    response: dict = await discovery.response(discovery_request, xds_type.value)
    if response['version_info'] == discovery_request.version_info:
        ret = 'No changes'
        code = config.no_changes_response_code
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
        f"client_ip:{discovery_request.node.metadata.get('ipv4', '-')}",
        f"client_version:{discovery_request.envoy_version}",
        f"response_code:{code}",
        f"xds_type:{xds_type.value}"
    ]
    metrics_tags += [f"resource:{resource}" for resource in discovery_request.resource_names]
    stats.increment('discovery.rq_total', tags=metrics_tags)
    add_log_context(
        resource_names=discovery_request.resource_names,
        envoy_ver=discovery_request.envoy_version
    )
    background_tasks.add_task(schedule.run_pending)
    return UJSONResponse(content=ret, status_code=code)
