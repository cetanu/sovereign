import yaml
from collections import defaultdict
from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder
from sovereign import discovery, config, json_response_class
from sovereign.discovery import DiscoveryTypes
from sovereign.statistics import stats
from sovereign.utils.mock import mock_discovery_request
from sovereign.sources import match_node

router = APIRouter()


@router.get(
    '/xds_dump',
    summary='Displays all xDS resources as JSON'
)
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
    ret['resources'] += response.get('resources', [])
    safe_response = jsonable_encoder(ret)
    return json_response_class(content=safe_response)


@router.get(
    '/source_dump',
    summary='Displays all sources that this Sovereign has polled as JSON'
)
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
    return json_response_class(content=safe_response)


@router.get(
    '/config',
    summary='Display the current Sovereign configuration'
)
def show_configuration():
    safe_response = jsonable_encoder(config.show())
    return json_response_class(content=safe_response)


@router.get(
    '/stats',
    summary='Displays all metrics emitted and their counters'
)
def show_stats():
    return json_response_class(content=stats.emitted)
