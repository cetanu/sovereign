from collections import defaultdict
from fastapi import APIRouter, Query, Path, Cookie
from fastapi.encoders import jsonable_encoder
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from sovereign import html_templates, discovery, XDS_TEMPLATES
from sovereign.discovery import DiscoveryTypes
from sovereign.sources import available_service_clusters, _metadata
from sovereign.utils.mock import mock_discovery_request

router = APIRouter()

all_types = [t.value for t in DiscoveryTypes]


@router.get('/', summary='Redirect to resource interface')
async def ui_main():
    return RedirectResponse(url=f'/ui/resources/{all_types[0]}')


@router.get(
    '/set-version',
    summary='Filter the UI by a certain Envoy Version (stores a Cookie)'
)
async def set_envoy_version(
        request: Request,
        version: str = Query('__any__', title='The clients envoy version to emulate in this XDS request'),
):
    url = request.headers.get('Referer', '/ui')
    response = RedirectResponse(url=url)
    response.set_cookie(key='envoy_version', value=version, max_age=3600)
    return response


@router.get(
    '/set-service-cluster',
    summary='Filter the UI by a certain service cluster (stores a Cookie)'
)
async def set_service_cluster(
        request: Request,
        service_cluster: str = Query('__any__', title='The clients envoy version to emulate in this XDS request'),
):
    url = request.headers.get('Referer', '/ui')
    response = RedirectResponse(url=url)
    response.set_cookie(key='service_cluster', value=service_cluster, max_age=3600)
    return response


@router.get(
    '/resources/{xds_type}',
    summary='List available resources for a given xDS type'
)
async def resources(
        request: Request,
        xds_type: DiscoveryTypes = Path('clusters', title='xDS type', description='The type of request'),
        region: str = Query(None, title='The clients region to emulate in this XDS request'),
        service_cluster: str = Cookie('*', title='The clients service cluster to emulate in this XDS request'),
        envoy_version: str = Cookie('__any__', title='The clients envoy version to emulate in this XDS request')
):
    ret = defaultdict(list)
    try:
        response = await discovery.response(
            request=mock_discovery_request(
                service_cluster=service_cluster,
                resource_names=[],
                version=envoy_version,
                region=region
            ),
            xds_type=xds_type.value
        )
    except KeyError:
        ret['resources'] = []
    else:
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
            'version': envoy_version,
            'available_versions': list(XDS_TEMPLATES.keys()),
            'service_cluster': service_cluster,
            'available_service_clusters': available_service_clusters(),
            'last_update': str(_metadata),
        })


@router.get(
    '/resources/{xds_type}/{resource_name}',
    summary='Return JSON representation of a resource'
)
async def resource(
        xds_type: DiscoveryTypes = Path('clusters', title='xDS type', description='The type of request'),
        resource_name: str = Path(..., title='Name of the resource to view'),
        region: str = Query(None, title='The clients region to emulate in this XDS request'),
        service_cluster: str = Cookie('*', title='The clients service cluster to emulate in this XDS request'),
        envoy_version: str = Cookie('__any__', title='The clients envoy version to emulate in this XDS request')
):
    response = await discovery.response(
        request=mock_discovery_request(
            service_cluster=service_cluster,
            resource_names=[resource_name],
            version=envoy_version,
            region=region
        ),
        xds_type=xds_type.value
    )
    safe_response = jsonable_encoder(response)
    return JSONResponse(content=safe_response)


@router.get(
    '/resources/routes/{route_configuration}/{virtual_host}',
    summary='Return JSON representation of Virtual Hosts'
)
async def virtual_hosts(
        route_configuration: str = Path(..., title='Name of the route configuration'),
        virtual_host: str = Path(..., title='Name of the resource to view'),
        region: str = Query(None, title='The clients region to emulate in this XDS request'),
        service_cluster: str = Cookie('*', title='The clients service cluster to emulate in this XDS request'),
        envoy_version: str = Cookie('__any__', title='The clients envoy version to emulate in this XDS request')
):
    response = await discovery.response(
        request=mock_discovery_request(
            service_cluster=service_cluster,
            resource_names=[route_configuration],
            version=envoy_version,
            region=region
        ),
        xds_type='routes'
    )
    if isinstance(response, dict):
        route_configs = [
            resource_
            for resource_ in response.get('resources', [])
            if resource_['name'] == route_configuration
        ]
        for route_config in route_configs:
            for vhost in route_config['virtual_hosts']:
                if vhost['name'] == virtual_host:
                    return JSONResponse(content=vhost)
            break
