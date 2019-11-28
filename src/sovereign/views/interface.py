from collections import defaultdict
from fastapi import APIRouter, Query, Path, Cookie
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from sovereign import html_templates, discovery, XDS_TEMPLATES
from sovereign.discovery import DiscoveryTypes
from sovereign.utils.mock import mock_discovery_request

router = APIRouter()

all_types = [t.value for t in DiscoveryTypes]


@router.get('/')
async def ui_main():
    return RedirectResponse(url=f'/ui/resources/{all_types[0]}')


@router.get('/set-version')
async def set_envoy_version(
    request: Request,
    version: str = Query('__any__', title='The clients envoy version to emulate in this XDS request'),
):
    url = request.headers.get('Referer', '/ui')
    response = RedirectResponse(url=url)
    response.set_cookie(key='envoy_version', value=version)
    return response


@router.get('/resources/{xds_type}')
async def resources(
        request: Request,
        xds_type: DiscoveryTypes = Path('clusters', title='xDS type', description='The type of request'),
        service_cluster: str = Query('*', title='The clients service cluster to emulate in this XDS request'),
        region: str = Query(None, title='The clients region to emulate in this XDS request'),
        version: str = Query('__any__', title='The clients envoy version to emulate in this XDS request'),
        envoy_version: str = Cookie(None, title='A non default envoy version has been selected')
):
    ret = defaultdict(list)
    if envoy_version is not None:
        version = envoy_version
    mock_request = mock_discovery_request(
        service_cluster=service_cluster,
        resource_names=[],
        version=version,
        region=region
    )
    response = await discovery.response(
        request=mock_request,
        xds_type=xds_type.value
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
            'all_types': all_types,
            'version': version,
            'available_versions': list(XDS_TEMPLATES.keys()),
        })


@router.get('/resources/{xds_type}/{resource_name}')
async def resource(
        xds_type: DiscoveryTypes = Path('clusters', title='xDS type', description='The type of request'),
        resource_name: str = Path(..., title='Name of the resource to view'),
        service_cluster: str = Query('*', title='The clients service cluster to emulate in this XDS request'),
        region: str = Query(None, title='The clients region to emulate in this XDS request'),
        version: str = Query('__any__', title='The clients envoy version to emulate in this XDS request'),
        envoy_version: str = Cookie(None, title='A non default envoy version has been selected')
):

    if envoy_version is not None:
        version = envoy_version
    mock_request = mock_discovery_request(
        service_cluster=service_cluster,
        resource_names=[],
        version=version,
        region=region
    )
    response = await discovery.response(
        request=mock_request,
        xds_type=xds_type.value
    )
    if isinstance(response, dict):
        for res in response.get('resources', []):
            name = res.get('name') or res['cluster_name']
            if name == resource_name:
                return JSONResponse(content=res)


@router.get('/resources/routes/{route_configuration}/{virtual_host}')
async def virtual_hosts(
        route_configuration: str = Path(..., title='Name of the route configuration'),
        virtual_host: str = Path(..., title='Name of the resource to view'),
        service_cluster: str = Query('*', title='The clients service cluster to emulate in this XDS request'),
        region: str = Query(None, title='The clients region to emulate in this XDS request'),
        version: str = Query('__any__', title='The clients envoy version to emulate in this XDS request'),
        envoy_version: str = Cookie(None, title='A non default envoy version has been selected')
):
    if envoy_version is not None:
        version = envoy_version
    mock_request = mock_discovery_request(
        service_cluster=service_cluster,
        resource_names=[],
        version=version,
        region=region
    )
    response = await discovery.response(
        request=mock_request,
        xds_type='routes'
    )
    if isinstance(response, dict):
        route_config = [
            r for r in response.get('resources', [])
            if r['name'] == route_configuration
        ][0]

        for vhost in route_config['virtual_hosts']:
            if vhost['name'] == virtual_host:
                return JSONResponse(content=vhost)
