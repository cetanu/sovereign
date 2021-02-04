from fastapi import Body, Header
from fastapi.routing import APIRouter
from fastapi.responses import Response
from sovereign.logs import add_log_context
from sovereign import discovery
from sovereign.sources import memoized_templates as nodes
from sovereign.schemas import DiscoveryRequest, DiscoveryResponse
from sovereign.statistics import stats
from sovereign.utils.auth import authenticate

router = APIRouter()

type_urls = {
    'listeners': 'type.googleapis.com/envoy.api.{version}.Listener',
    'clusters': 'type.googleapis.com/envoy.api.{version}.Cluster',
    'endpoints': 'type.googleapis.com/envoy.api.{version}.ClusterLoadAssignment',
    'secrets': 'type.googleapis.com/envoy.api.{version}.auth.Secret',
    'routes': 'type.googleapis.com/envoy.api.{version}.RouteConfiguration',
    'scoped-routes': 'type.googleapis.com/envoy.api.{version}.ScopedRouteConfiguration',
}


def response_headers(discovery_request, response, xds):
    return {
        'X-Sovereign-Client-Build': discovery_request.envoy_version,
        'X-Sovereign-Client-Version': discovery_request.version_info,
        'X-Sovereign-Requested-Resources': ','.join(discovery_request.resource_names) or 'all',
        'X-Sovereign-Requested-Type': xds,
        'X-Sovereign-Response-Version': response.version_info
    }


@router.post(
    '/{version}/discovery:{xds_type}',
    summary='Envoy Discovery Service Endpoint',
    response_model=DiscoveryResponse,
    responses={
        200: {'description': 'New resources provided'},
        304: {'description': 'Resources are up-to-date'},
        404: {'description': 'No resources found'},
    }
)
async def discovery_response(
        version: str,
        xds_type: discovery.DiscoveryTypes,
        discovery_request: DiscoveryRequest = Body(None),
        host: str = Header('no_host_provided'),
):
    authenticate(discovery_request)
    xds = xds_type.value
    type_url = type_urls[xds].format(version=version)
    discovery_request.type_url = type_url
    discovery_request.desired_controlplane = host
    uid = discovery_request.uid
    add_log_context(
        resource_names=discovery_request.resource_names,
        envoy_ver=discovery_request.envoy_version
    )

    if cached_data := nodes.get_node(uid, xds):
        stats.increment(f'discovery.{xds}.cache_hit')
        headers = response_headers(discovery_request, cached_data, xds)
        if cached_data.version_info == discovery_request.version_info:
            return not_modified(headers)
        return Response(cached_data.rendered, headers=headers, media_type='application/json')

    response = await discovery.response(discovery_request, xds, host)
    headers = response_headers(discovery_request, response, xds)

    if response.version_info == discovery_request.version_info:
        return not_modified(headers)
    elif len(response.resources) == 0:
        return Response(status_code=404, headers=headers)
    elif response.version_info != discovery_request.version_info:
        nodes.add_node(uid=uid, xds_type=xds, template=response)
        stats.increment(f'discovery.{xds}.cache_miss')
        return Response(nodes.get_node(uid, xds).rendered, headers=headers, media_type='application/json')
    return Response(content='Resources could not be determined', status_code=500)


def not_modified(headers):
    return Response(status_code=304, headers=headers)
