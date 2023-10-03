from typing import List, Dict, Any
from collections import defaultdict
from fastapi import APIRouter, Query, Path, Cookie
from fastapi.encoders import jsonable_encoder
from fastapi.requests import Request
from fastapi.responses import RedirectResponse, JSONResponse, Response
from sovereign import html_templates, XDS_TEMPLATES
from sovereign.discovery import DiscoveryTypes
from sovereign import poller, json_response_class
from sovereign.utils.mock import mock_discovery_request
from sovereign.views.discovery import perform_discovery

router = APIRouter()

all_types = [t.value for t in DiscoveryTypes]


@router.get("/")
async def ui_main(request: Request) -> Response:
    try:
        return html_templates.TemplateResponse(
            name="base.html",
            media_type="text/html",
            context={
                "request": request,
                "all_types": all_types,
                "last_update": str(poller.last_updated),
            },
        )
    except IndexError:
        return html_templates.TemplateResponse(
            name="err.html",
            media_type="text/html",
            context={
                "request": request,
                "title": "No resource types configured",
                "message": "A template should be defined for every resource "
                "type that you want your envoy proxies to discover.",
                "doc_link": "https://vsyrakis.bitbucket.io/sovereign/docs/tutorial/templates/",
            },
        )


@router.get(
    "/set-version", summary="Filter the UI by a certain Envoy Version (stores a Cookie)"
)
async def set_envoy_version(
    request: Request,
    version: str = Query(
        "__any__", title="The clients envoy version to emulate in this XDS request"
    ),
) -> Response:
    url = request.headers.get("Referer", "/ui")
    response = RedirectResponse(url=url)
    response.set_cookie(key="envoy_version", value=version)
    return response


@router.get(
    "/set-service-cluster",
    summary="Filter the UI by a certain service cluster (stores a Cookie)",
)
async def set_service_cluster(
    request: Request,
    service_cluster: str = Query(
        "__any__", title="The clients envoy version to emulate in this XDS request"
    ),
) -> Response:
    url = request.headers.get("Referer", "/ui")
    response = RedirectResponse(url=url)
    response.set_cookie(key="service_cluster", value=service_cluster)
    return response


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
    service_cluster: str = Cookie(
        "*", title="The clients service cluster to emulate in this XDS request"
    ),
    envoy_version: str = Cookie(
        "__any__", title="The clients envoy version to emulate in this XDS request"
    ),
) -> Response:
    ret: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    try:
        response = await perform_discovery(
            req=mock_discovery_request(
                service_cluster=service_cluster,
                resource_names=[],
                version=envoy_version,
                region=region,
            ),
            api_version=api_version,
            resource_type=xds_type,
            skip_auth=True,
        )
    except KeyError:
        ret["resources"] = []
    else:
        ret["resources"] += response.deserialize_resources()
    return html_templates.TemplateResponse(
        name="resources.html",
        media_type="text/html",
        context={
            "resources": ret["resources"],
            "request": request,
            "resource_type": xds_type,
            "all_types": all_types,
            "version": envoy_version,
            "available_versions": list(XDS_TEMPLATES.keys()),
            "service_cluster": service_cluster,
            "available_service_clusters": poller.match_keys,
            "last_update": str(poller.last_updated),
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
    service_cluster: str = Cookie(
        "*", title="The clients service cluster to emulate in this XDS request"
    ),
    envoy_version: str = Cookie(
        "__any__", title="The clients envoy version to emulate in this XDS request"
    ),
) -> Response:
    response = await perform_discovery(
        req=mock_discovery_request(
            service_cluster=service_cluster,
            resource_names=[resource_name],
            version=envoy_version,
            region=region,
        ),
        api_version=api_version,
        resource_type=xds_type,
        skip_auth=True,
    )
    return Response(response.rendered, media_type="application/json")


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
    service_cluster: str = Cookie(
        "*", title="The clients service cluster to emulate in this XDS request"
    ),
    envoy_version: str = Cookie(
        "__any__", title="The clients envoy version to emulate in this XDS request"
    ),
) -> Response:
    response = await perform_discovery(
        req=mock_discovery_request(
            service_cluster=service_cluster,
            resource_names=[route_configuration],
            version=envoy_version,
            region=region,
        ),
        api_version=api_version,
        resource_type="routes",
        skip_auth=True,
    )
    route_configs = [
        resource_
        for resource_ in response.deserialize_resources()
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
        break
    return JSONResponse(content={})
