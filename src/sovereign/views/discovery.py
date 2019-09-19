import schedule
from fastapi import Body, BackgroundTasks
from fastapi.routing import APIRouter
from starlette.responses import UJSONResponse
from sovereign import discovery, statsd, config
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
        r: DiscoveryRequest = Body(None),
):
    background_tasks.add_task(schedule.run_pending)

    authenticate(r)
    response = await discovery.response(r, xds_type.value)

    if response['version_info'] == r.version_info:
        ret = 'No changes'
        code = config.no_changes_response_code
    elif len(response['resources']) == 0:
        ret = 'No resources found'
        code = 404
    elif response['version_info'] != r.version_info:
        ret = response
        code = 200
    else:
        ret = 'Unknown Error'
        code = 500

    try:
        client_ip = r.node.metadata.get('ipv4')
    except KeyError:
        client_ip = '-'

    metrics_tags = [
        f"client_ip:{client_ip}",
        f"client_version:{r.envoy_version}",
        f"response_code:{code}",
        f"xds_type:{xds_type.value}"
    ]
    metrics_tags += [f"resource:{resource}" for resource in r.resource_names]
    statsd.increment('discovery.rq_total', tags=metrics_tags)
    return UJSONResponse(content=ret, status_code=code)
