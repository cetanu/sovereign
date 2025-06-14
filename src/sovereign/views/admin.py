import json
from collections import defaultdict
from typing import Any, Dict, List

import yaml
from fastapi import APIRouter, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from sovereign import config, poller, stats, template_context
from sovereign.discovery import select_template
from sovereign.utils.mock import mock_discovery_request
from sovereign.views.discovery import perform_discovery

router = APIRouter()


@router.get("/xds_dump", summary="Displays all xDS resources as JSON")
async def display_config(
    xds_type: str = Query(
        ..., title="xDS type", description="The type of request", examples=["clusters"]
    ),
    service_cluster: str = Query(
        "*", title="The clients service cluster to emulate in this XDS request"
    ),
    metadata: str = Query(
        None, title="The clients metadata to emulate in this XDS request"
    ),
    resource_names: List[str] = Query([], title="Envoy Resource names to request"),
    region: str = Query(
        None, title="The clients region to emulate in this XDS request"
    ),
    version: str = Query(
        "1.11.1", title="The clients envoy version to emulate in this XDS request"
    ),
) -> JSONResponse:
    ret: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    try:
        if metadata:
            json_decoded_metadata = json.loads(metadata)
        else:
            json_decoded_metadata = {}
    except json.JSONDecodeError:
        return JSONResponse(
            content={"error": "Invalid JSON in query parameter 'metadata'"},
            status_code=400,
        )
    mock_request = mock_discovery_request(
        service_cluster=service_cluster,
        resource_names=resource_names,
        version=version,
        region=region,
        metadata=json_decoded_metadata,
    )
    response = await perform_discovery(mock_request, "v3", xds_type, skip_auth=True)
    ret["resources"] += response.resources
    safe_response = jsonable_encoder(ret)
    return JSONResponse(content=safe_response)


@router.get(
    "/debug_template",
    summary="Dumps raw representation of template output before serialization/extra processing",
)
async def debug_template(
    xds_type: str = Query(
        ..., title="xDS type", description="The type of request", examples=["clusters"]
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
    template = select_template(mock_request, xds_type)
    context = template_context.get_context(mock_request, template)
    context = dict(
        discovery_request=mock_request,
        host_header="debug",
        resource_names=mock_request.resources,
        **context,
    )
    raw_template_content = template(**context)
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
    assert poller is not None  # how else would there be sources
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


@router.get("/templates", summary="Display the currently loaded XDS templates")
def show_templates() -> JSONResponse:
    safe_response = jsonable_encoder(config.xds_templates())
    return JSONResponse(content=safe_response)
