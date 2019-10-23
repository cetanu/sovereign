import yaml
from collections import defaultdict
from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder
from starlette.responses import UJSONResponse
from sovereign.discovery import DiscoveryTypes
from sovereign.utils.mock import mock_discovery_request
from sovereign import discovery, config
from sovereign.sources import match_node
from sovereign.decorators import cache

router = APIRouter()


@router.get('/xds_dump')
async def display_config(
        xds_type: DiscoveryTypes = Query(..., title='xDS type', description='The type of request', example='clusters'),
        service_cluster: str = Query('*', title='The clients service cluster to emulate in this XDS request'),
        resource_names: str = Query('', title='Envoy Resource names to request'),
        region: str = Query(None, title='The clients region to emulate in this XDS request'),
        version: str = Query('1.11.1', title='The clients envoy version to emulate in this XDS request')
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
        xds_type=xds_type.value
    )
    if isinstance(response, dict):
        ret['resources'] += response.get('resources') or []

    return UJSONResponse(content=ret)


@router.get('/source_dump')
def instances(
        service_cluster: str = Query('*', title='The clients service cluster to emulate in this XDS request'),
        modified: str = Query('yes',
                              title='Whether the sources should run Modifiers/Global Modifiers prior to being returned')
):
    args = {
        'modify': yaml.safe_load(modified),
        'request': mock_discovery_request(
            service_cluster=service_cluster
        )
    }
    ret = match_node(**args)
    safe_response = jsonable_encoder(ret)
    return UJSONResponse(content=safe_response)


@router.get('/cache_dump')
def show_cached_keys():
    # noinspection PyProtectedMember
    return UJSONResponse(content=list(sorted(cache._cache.keys())))


@router.get('/config')
def show_configuration():
    safe_response = jsonable_encoder(config.show())
    return UJSONResponse(content=safe_response)
