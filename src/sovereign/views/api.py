import json
from typing import Optional

from fastapi import APIRouter, Query, Path
from fastapi.responses import Response

from sovereign import cache
from sovereign.schemas import DiscoveryTypes
from sovereign.utils.mock import mock_discovery_request

router = APIRouter()


@router.get("/resources/{resource_type}", summary="Get resources for a given type")
async def resource(
    resource_type: DiscoveryTypes = Path(title="xDS Resource type"),
    resource_name: Optional[str] = Query(None, title="Resource name"),
    api_version: Optional[str] = Query("v3", title="Envoy API version"),
    service_cluster: Optional[str] = Query("*", title="Envoy Service cluster"),
    region: Optional[str] = Query(None, title="Locality Zone"),
    version: Optional[str] = Query(None, title="Envoy Semantic Version"),
) -> Response:
    kwargs = dict(
        api_version=api_version,
        resource_type=DiscoveryTypes(resource_type).value,
        resource_names=resource_name,
        version=version,
        region=region,
        expressions=[f"cluster={service_cluster}"],
    )
    req = mock_discovery_request(**{k: v for k, v in kwargs.items() if v is not None})
    response = await cache.blocking_read(req)
    if content := getattr(response, "text", None):
        return Response(content, media_type="application/json")
    else:
        return Response(
            json.dumps({"title": "No resources found", "status": 404}),
            media_type="application/json+problem",
        )
