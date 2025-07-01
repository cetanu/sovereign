import json
from collections import defaultdict
from typing import Any, Dict, List

from fastapi import APIRouter, Cookie, Path, Query
from fastapi.encoders import jsonable_encoder
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from sovereign import html_templates, cache
from sovereign.schemas import DiscoveryTypes, XDS_TEMPLATES
from sovereign.response_class import json_response_class
from sovereign.utils.mock import mock_discovery_request

router = APIRouter()

all_types = [t.value for t in DiscoveryTypes]


@router.get("/")
@router.get("/resources")
async def ui_main(request: Request) -> HTMLResponse:
    try:
        return html_templates.TemplateResponse(
            request=request,
            name="base.html",
            media_type="text/html",
            context={
                "all_types": all_types,
            },
        )
    except IndexError:
        return html_templates.TemplateResponse(
            request=request,
            name="err.html",
            media_type="text/html",
            context={
                "title": "No resource types configured",
                "message": "A template should be defined for every resource "
                "type that you want your envoy proxies to discover.",
                "doc_link": "https://developer.atlassian.com/platform/sovereign/tutorial/templates/#templates",
            },
        )


@router.get(
    "/resources/{xds_type}", summary="List available resources for a given xDS type"
)
async def resources(
    request: Request,
    xds_type: str = Path(title="xDS type", description="The type of request"),
    region: str = Query(
        None, title="The clients region to emulate in this XDS request"
    ),
    api_version: str = Query("v2", title="The desired Envoy API version"),
    node_expression: str = Cookie(
        "cluster=*", title="Node expression to filter resources with"
    ),
    envoy_version: str = Cookie(
        "__any__", title="The clients envoy version to emulate in this XDS request"
    ),
    debug: int = Query(0, title="Show debug information on errors"),
) -> HTMLResponse:
    ret: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    response = None
    mock_request = mock_discovery_request(
        api_version,
        xds_type,
        version=envoy_version,
        region=region,
        expressions=node_expression.split(),
    )
    response = await cache.blocking_read(mock_request)
    if response:
        ret["resources"] = json.loads(response.text).get("resources", [])

    return html_templates.TemplateResponse(
        request=request,
        name="resources.html",
        media_type="text/html",
        context={
            "show_debuginfo": True if debug else False,
            "discovery_response": response,
            "discovery_request": mock_request,
            "resources": ret["resources"],
            "resource_type": xds_type,
            "all_types": all_types,
            "version": envoy_version,
            "available_versions": list(XDS_TEMPLATES.keys()),
        },
    )


@router.get(
    "/resources/{xds_type}/{resource_name}",
    summary="Return JSON representation of a resource",
)
async def resource(
    xds_type: str = Path(title="xDS type", description="The type of request"),
    resource_name: str = Path(..., title="Name of the resource to view"),
    region: str = Query(
        None, title="The clients region to emulate in this XDS request"
    ),
    api_version: str = Query("v2", title="The desired Envoy API version"),
    node_expression: str = Cookie(
        "cluster=*", title="Node expression to filter resources with"
    ),
    envoy_version: str = Cookie(
        "__any__", title="The clients envoy version to emulate in this XDS request"
    ),
) -> Response:
    mock_request = mock_discovery_request(
        api_version,
        xds_type,
        version=envoy_version,
        region=region,
        expressions=node_expression.split(),
    )
    if response := await cache.blocking_read(mock_request):
        for res in json.loads(response.text).get("resources", []):
            if res.get("name", res.get("cluster_name")) == resource_name:
                safe_response = jsonable_encoder(res)
                try:
                    return json_response_class(content=safe_response)
                except TypeError:
                    return JSONResponse(content=safe_response)
    return Response(
        json.dumps({"title": "No resources found", "status": 404}),
        media_type="application/json+problem",
    )


@router.get(
    "/resources/routes/{route_configuration}/{virtual_host}",
    summary="Return JSON representation of Virtual Hosts",
)
async def virtual_hosts(
    route_configuration: str = Path(..., title="Name of the route configuration"),
    virtual_host: str = Path(..., title="Name of the resource to view"),
    region: str = Query(
        None, title="The clients region to emulate in this XDS request"
    ),
    api_version: str = Query("v2", title="The desired Envoy API version"),
    node_expression: str = Cookie(
        "cluster=*", title="Node expression to filter resources with"
    ),
    envoy_version: str = Cookie(
        "__any__", title="The clients envoy version to emulate in this XDS request"
    ),
) -> Response:
    mock_request = mock_discovery_request(
        api_version,
        "routes",
        version=envoy_version,
        region=region,
        expressions=node_expression.split(),
    )
    if response := await cache.blocking_read(mock_request):
        route_configs = [
            resource_
            for resource_ in json.loads(response.text).get("resources", [])
            if resource_["name"] == route_configuration
        ]
        for route_config in route_configs:
            for vhost in route_config["virtual_hosts"]:
                if vhost["name"] == virtual_host:
                    safe_response = jsonable_encoder(vhost)
                    try:
                        return json_response_class(content=safe_response)
                    except TypeError:
                        return JSONResponse(content=safe_response)
    return Response(
        json.dumps({"title": "No resources found", "status": 404}),
        media_type="application/json+problem",
    )
