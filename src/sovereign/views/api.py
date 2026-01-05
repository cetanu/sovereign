import json
from typing import Annotated, Optional

from fastapi import APIRouter, Path, Query
from fastapi.responses import Response

from sovereign.cache import Entry
from sovereign.configuration import ConfiguredResourceTypes, config
from sovereign.utils.mock import mock_discovery_request
from sovereign.v2.web import wait_for_discovery_response
from sovereign.views import reader

router = APIRouter()


def _traverse(data, prefix, expressions):
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            yield from _traverse(value, path, expressions)
        else:
            yield f"{path}={value}"


def expand_metadata_to_expr(m):
    exprs = []
    yield from _traverse(m, "", exprs)


# noinspection DuplicatedCode
@router.get("/resources/{resource_type}", summary="Get resources for a given type")
async def resource(
    resource_type: Annotated[ConfiguredResourceTypes, Path(title="xDS Resource type")],
    resource_name: Optional[str] = Query(None, title="Resource name"),
    api_version: Optional[str] = Query("v3", title="Envoy API version"),
    service_cluster: Optional[str] = Query("*", title="Envoy Service cluster"),
    region: Optional[str] = Query(None, title="Locality Zone"),
    version: Optional[str] = Query(None, title="Envoy Semantic Version"),
    metadata: Optional[str] = Query(None, title="Envoy node metadata to filter by"),
) -> Response:
    # todo: rewrite for worker v2

    expressions = [f"cluster={service_cluster}"]
    try:
        data = {"metadata": json.loads(metadata or "{}")}
        for expr in expand_metadata_to_expr(data):
            expressions.append(expr)
    except Exception:
        pass
    kwargs = {
        "api_version": api_version,
        "resource_type": ConfiguredResourceTypes(resource_type).value,
        "resource_names": resource_name,
        "version": version,
        "region": region,
        "expressions": expressions,
    }
    req = mock_discovery_request(**{k: v for k, v in kwargs.items() if v is not None})  # type: ignore

    entry: Entry | None = None

    if config.worker_v2_enabled:
        # we're set up to use v2 of the worker
        discovery_response = await wait_for_discovery_response(req)
        if discovery_response is not None:
            entry = Entry(
                text=discovery_response.model_dump_json(indent=None),
                len=len(discovery_response.resources),
                version=discovery_response.version_info,
                node=req.node,
            )

    else:
        entry = await reader.blocking_read(req)  # ty: ignore[possibly-missing-attribute]

    if content := getattr(entry, "text", None):
        return Response(content, media_type="application/json")
    else:
        return Response(
            json.dumps({"title": "No resources found", "status": 404}),
            media_type="application/json+problem",
        )
