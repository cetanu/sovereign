import yaml
from typing import Any, Dict, List
from collections import defaultdict
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from sovereign import discovery, config, stats, poller, template_context
from sovereign.discovery import DiscoveryTypes, select_template
from sovereign.utils.mock import mock_discovery_request

router = APIRouter()


@router.get("/xds_dump", summary="Displays all xDS resources as JSON")
async def display_config(
    xds_type: DiscoveryTypes = Query(
        ..., title="xDS type", description="The type of request", example="clusters"
    ),
    service_cluster: str = Query(
        "*", title="The clients service cluster to emulate in this XDS request"
    ),
    resource_names: str = Query("", title="Envoy Resource names to request"),
    region: str = Query(
        None, title="The clients region to emulate in this XDS request"
    ),
    version: str = Query(
        "1.11.1", title="The clients envoy version to emulate in this XDS request"
    ),
) -> JSONResponse:
    ret: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    mock_request = mock_discovery_request(
        service_cluster=service_cluster,
        resource_names=resource_names.split(","),
        version=version,
        region=region,
    )
    response = await discovery.response(request=mock_request, xds_type=xds_type)
    ret["resources"] += response.resources
    safe_response = jsonable_encoder(ret)
    return JSONResponse(content=safe_response)


@router.get(
    "/debug_template",
    summary="Dumps raw representation of template output before serialization/extra processing",
)
async def debug_template(
    xds_type: DiscoveryTypes = Query(
        ..., title="xDS type", description="The type of request", example="clusters"
    ),
    service_cluster: str = Query(
        "*", title="The clients service cluster to emulate in this XDS request"
    ),
    resource_names: str = Query("", title="Envoy Resource names to request"),
    region: str = Query(
        None, title="The clients region to emulate in this XDS request"
    ),
    version: str = Query(
        "1.11.1", title="The clients envoy version to emulate in this XDS request"
    ),
) -> JSONResponse:
    mock_request = mock_discovery_request(
        service_cluster=service_cluster,
        resource_names=resource_names.split(","),
        version=version,
        region=region,
    )
    template = select_template(mock_request, xds_type.value)
    context = template_context.get_context(mock_request, template)
    context = dict(
        discovery_request=mock_request,
        host_header="debug",
        resource_names=mock_request.resources,
        **context,
    )
    raw_template_content = await template(**context)
    safe_response = jsonable_encoder(raw_template_content)
    return JSONResponse(content=safe_response)


@router.get(
    "/source_dump",
    summary="Displays all sources that this Sovereign has polled as JSON",
)
def instances(
    service_cluster: str = Query(
        "*", title="The clients service cluster to emulate in this XDS request"
    ),
    modified: str = Query(
        "yes",
        title="Whether the sources should run Modifiers/Global Modifiers prior to being returned",
    ),
) -> JSONResponse:
    node = mock_discovery_request(service_cluster=service_cluster).node
    args = {
        "modify": yaml.safe_load(modified),
        "node_value": poller.extract_node_key(node),
    }
    ret = poller.match_node(**args)
    safe_response = jsonable_encoder(ret)
    return JSONResponse(content=safe_response)


@router.get("/config", summary="Display the current Sovereign configuration")
def show_configuration() -> JSONResponse:
    safe_response = jsonable_encoder(config.show())
    return JSONResponse(content=safe_response)


@router.get("/stats", summary="Displays all metrics emitted and their counters")
def show_stats() -> JSONResponse:
    return JSONResponse(content=stats.emitted)
