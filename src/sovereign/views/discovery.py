from fastapi import Body, Header
from fastapi.routing import APIRouter
from fastapi.responses import Response
from sovereign.logs import add_log_context
from sovereign import discovery
from sovereign.sources import memoized_templates as nodes
from sovereign.schemas import DiscoveryRequest, DiscoveryResponse, ProcessedTemplate
from sovereign.statistics import stats
from sovereign.utils.auth import authenticate

router = APIRouter()

type_urls = {
    'v2': {
        'listeners': 'type.googleapis.com/envoy.api.v2.Listener',
        'clusters': 'type.googleapis.com/envoy.api.v2.Cluster',
        'endpoints': 'type.googleapis.com/envoy.api.v2.ClusterLoadAssignment',
        'secrets': 'type.googleapis.com/envoy.api.v2.auth.Secret',
        'routes': 'type.googleapis.com/envoy.api.v2.RouteConfiguration',
        'scoped-routes': 'type.googleapis.com/envoy.api.v2.ScopedRouteConfiguration',
    },
    'v3': {
        'listeners': 'type.googleapis.com/envoy.config.listener.v3.Listener',
        'clusters': 'type.googleapis.com/envoy.config.cluster.v3.Cluster',
        'routes': 'type.googleapis.com/envoy.config.route.v3.RouteConfiguration',
        'scoped-routes': 'type.googleapis.com/envoy.config.route.v3.ScopedRouteConfiguration',
    },
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
    xds = xds_type.value
    discovery_request.desired_controlplane = host
    add_log_context(
        resource_names=discovery_request.resource_names,
        envoy_ver=discovery_request.envoy_version
    )
    response = await perform_discovery(discovery_request, version, xds, skip_auth=False)
    headers = response_headers(discovery_request, response, xds)
    if response.version_info == discovery_request.version_info:
        return not_modified(headers)
    elif len(response.resources) == 0:
        return Response(status_code=404, headers=headers)
    elif response.version_info != discovery_request.version_info:
        return Response(response.rendered, headers=headers, media_type='application/json')
    return Response(content='Resources could not be determined', status_code=500)


async def perform_discovery(req, api_version, xds, skip_auth=False) -> ProcessedTemplate:
    if not skip_auth:
        authenticate(req)
    try:
        type_url = type_urls[api_version][xds]
        req.type_url = type_url
    except TypeError:
        pass
    # Only run this block if the envoy proxy flags that it wants this behavior
    if req.node.metadata.get('enable_beta_caching'):
        # Attempt to retrieve cached data
        cached_data = nodes.get_node(req.uid, xds)
        if cached_data:
            stats.increment(f'discovery.{xds}.cache_hit')
            return cached_data
        else:
            # Perform normal discovery and then add it to the cache
            response = await discovery.response(req, xds)
            stats.increment(f'discovery.{xds}.cache_miss')
            nodes.add_node(uid=req.uid, xds_type=xds, template=response)
            return response
    return await discovery.response(req, xds)


def not_modified(headers):
    return Response(status_code=304, headers=headers)
