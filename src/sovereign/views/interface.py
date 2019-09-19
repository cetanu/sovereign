from collections import defaultdict
from fastapi import APIRouter, Query, Path
from starlette.requests import Request
from starlette.responses import JSONResponse
from sovereign import html_templates, discovery
from sovereign.discovery import DiscoveryTypes
from sovereign.utils.mock import mock_discovery_request

router = APIRouter()

all_types = [t.value for t in DiscoveryTypes]


@router.get('/{xds_type}')
async def resources(
        request: Request,
        xds_type: DiscoveryTypes = Path('clusters', title='xDS type', description='The type of request'),
        service_cluster: str = Query('*', title='The clients service cluster to emulate in this XDS request'),
        resource_names: str = Query('', title='Envoy Resource names to request'),
        region: str = Query(None, title='The clients region to emulate in this XDS request'),
        version: str = Query('1.11.1', title='The clients envoy version to emulate in this XDS request'),
):
    ret = defaultdict(list)
    mock_request = mock_discovery_request(
        service_cluster=service_cluster,
        resource_names=resource_names,
        version=version,
        region=region
    )
    response = await discovery.response(
        request=mock_request,
        xds=xds_type.value,
        debug=True
    )
    if isinstance(response, dict):
        ret['resources'] += response.get('resources') or []
    return html_templates.TemplateResponse(
        name='resources.html',
        media_type='text/html',
        context={
            'resources': ret['resources'],
            'request': request,
            'resource_type': xds_type.value,
            'all_types': all_types
        })


@router.get('/{xds_type}/{resource_name}')
async def resource(
        xds_type: DiscoveryTypes = Path('clusters', title='xDS type', description='The type of request'),
        resource_name: str = Path(..., title='Name of the resource to view'),
        service_cluster: str = Query('*', title='The clients service cluster to emulate in this XDS request'),
        resource_names: str = Query('', title='Envoy Resource names to request'),
        region: str = Query(None, title='The clients region to emulate in this XDS request'),
        version: str = Query('1.11.1', title='The clients envoy version to emulate in this XDS request'),
):
    mock_request = mock_discovery_request(
        service_cluster=service_cluster,
        resource_names=resource_names,
        version=version,
        region=region
    )
    response = await discovery.response(
        request=mock_request,
        xds=xds_type.value,
        debug=True
    )
    if isinstance(response, dict):
        for res in response.get('resources', []):
            if res['name'] == resource_name:
                return JSONResponse(content=res)


@router.get('/routes/{route_configuration}/{virtual_host}')
async def virtual_hosts(
        route_configuration: str = Path(..., title='Name of the route configuration'),
        virtual_host: str = Path(..., title='Name of the resource to view'),
        service_cluster: str = Query('*', title='The clients service cluster to emulate in this XDS request'),
        resource_names: str = Query('', title='Envoy Resource names to request'),
        region: str = Query(None, title='The clients region to emulate in this XDS request'),
        version: str = Query('1.11.1', title='The clients envoy version to emulate in this XDS request'),
):
    mock_request = mock_discovery_request(
        service_cluster=service_cluster,
        resource_names=resource_names,
        version=version,
        region=region
    )
    response = await discovery.response(
        request=mock_request,
        xds='routes',
        debug=True
    )
    if isinstance(response, dict):
        route_config = [
            r for r in response.get('resources', [])
            if r['name'] == route_configuration
        ][0]

        for vhost in route_config['virtual_hosts']:
            if vhost['name'] == virtual_host:
                return JSONResponse(content=vhost)
