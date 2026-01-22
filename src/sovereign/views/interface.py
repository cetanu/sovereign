import json
import logging
from collections import defaultdict
from typing import Any, Dict, List

from fastapi import APIRouter, Cookie, Path, Query
from fastapi.encoders import jsonable_encoder
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.templating import Jinja2Templates
from structlog.typing import FilteringBoundLogger

from sovereign import __version__
from sovereign.cache import Entry
from sovereign.configuration import XDS_TEMPLATES, ConfiguredResourceTypes, config
from sovereign.response_class import json_response_class
from sovereign.utils.mock import NodeExpressionError, mock_discovery_request
from sovereign.utils.resources import get_package_file
from sovereign.v2.logging import get_named_logger
from sovereign.v2.web import wait_for_discovery_response
from sovereign.views import reader

router = APIRouter()

all_types = [t.value for t in ConfiguredResourceTypes]

html_templates = Jinja2Templates(
    directory=str(get_package_file("sovereign", "templates"))
)


@router.get("/")
@router.get("/resources")
async def ui_main(request: Request) -> HTMLResponse:
    try:
        return html_templates.TemplateResponse(
            request=request,
            name="base.html",
            media_type="text/html",
            context={"all_types": all_types, "sovereign_version": __version__},
        )
    except IndexError:
        return html_templates.TemplateResponse(
            request=request,
            name="err.html",
            media_type="text/html",
            context={
                "title": "No resource types configured",
                "message": (
                    "A template should be defined for every resource "
                    "type that you want your envoy proxies to discover."
                ),
                "doc_link": "https://developer.atlassian.com/platform/sovereign/tutorial/templates/#templates",
                "sovereign_version": __version__,
            },
        )


# noinspection DuplicatedCode
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
    logger: FilteringBoundLogger = get_named_logger(
        f"{__name__}.{resources.__qualname__} ({__file__})",
        level=logging.INFO,
    )

    ret: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    try:
        mock_request = mock_discovery_request(
            api_version,
            xds_type,
            version=envoy_version,
            region=region,
            expressions=node_expression.split(),
        )
        clear_cookie = False
        error = None
    except NodeExpressionError as e:
        mock_request = mock_discovery_request(
            api_version,
            xds_type,
            version=envoy_version,
            region=region,
        )
        clear_cookie = True
        error = str(e)

    logger.debug("Making mock request", mock_request=mock_request)

    entry: Entry | None = None

    if config.worker_v2_enabled:
        # we're set up to use v2 of the worker
        discovery_response = await wait_for_discovery_response(mock_request)
        if discovery_response is not None:
            entry = Entry(
                text=discovery_response.model_dump_json(indent=None),
                len=len(discovery_response.resources),
                version=discovery_response.version_info,
                node=mock_request.node,
            )

    else:
        entry = await reader.blocking_read(mock_request)  # ty: ignore[possibly-missing-attribute]

    if entry:
        ret["resources"] = json.loads(entry.text).get("resources", [])

    resp = html_templates.TemplateResponse(
        request=request,
        name="resources.html",
        media_type="text/html",
        context={
            "show_debuginfo": True if debug else False,
            "discovery_response": entry,
            "discovery_request": mock_request,
            "resources": ret["resources"],
            "resource_type": xds_type,
            "all_types": all_types,
            "version": envoy_version,
            "available_versions": list(XDS_TEMPLATES.keys()),
            "error": error,
            "sovereign_version": __version__,
        },
    )
    if clear_cookie:
        resp.delete_cookie("node_expression", path="/ui/resources/")
    return resp


# noinspection DuplicatedCode
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
    logger: FilteringBoundLogger = get_named_logger(
        f"{__name__}.{resources.__qualname__} ({__file__})",
        level=logging.INFO,
    )

    mock_request = mock_discovery_request(
        api_version,
        xds_type,
        version=envoy_version,
        region=region,
        expressions=node_expression.split(),
    )

    logger.debug("Making mock request", mock_request=mock_request)

    entry: Entry | None = None

    if config.worker_v2_enabled:
        # we're set up to use v2 of the worker
        discovery_response = await wait_for_discovery_response(mock_request)
        if discovery_response is not None:
            entry = Entry(
                text=discovery_response.model_dump_json(indent=None),
                len=len(discovery_response.resources),
                version=discovery_response.version_info,
                node=mock_request.node,
            )

    else:
        entry = await reader.blocking_read(mock_request)  # ty: ignore[possibly-missing-attribute]

    if entry:
        for res in json.loads(entry.text).get("resources", []):
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


# noinspection DuplicatedCode
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
    logger: FilteringBoundLogger = get_named_logger(
        f"{__name__}.{virtual_hosts.__qualname__} ({__file__})",
        level=logging.INFO,
    )

    mock_request = mock_discovery_request(
        api_version,
        "routes",
        version=envoy_version,
        region=region,
        expressions=node_expression.split(),
    )

    logger.debug("Making mock request", mock_request=mock_request)

    entry: Entry | None = None

    if config.worker_v2_enabled:
        # we're set up to use v2 of the worker
        discovery_response = await wait_for_discovery_response(mock_request)
        if discovery_response is not None:
            entry = Entry(
                text=discovery_response.model_dump_json(indent=None),
                len=len(discovery_response.resources),
                version=discovery_response.version_info,
                node=mock_request.node,
            )

    else:
        entry = await reader.blocking_read(mock_request)  # ty: ignore[possibly-missing-attribute]

    if entry:
        route_configs = [
            resource_
            for resource_ in json.loads(entry.text).get("resources", [])
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
