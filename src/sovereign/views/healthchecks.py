from typing import List

import asyncio
import requests
from fastapi import Response
from fastapi.routing import APIRouter
from fastapi.responses import PlainTextResponse

from sovereign import __version__, cache
from sovereign.schemas import XDS_TEMPLATES
from sovereign.response_class import json_response_class
from sovereign.utils.mock import mock_discovery_request


router = APIRouter()


@router.get("/healthcheck", summary="Healthcheck (Does the server respond to HTTP?)")
async def health_check() -> Response:
    return PlainTextResponse("OK", status_code=200)


@router.get(
    "/deepcheck",
    summary="Deepcheck (Can the server render all configured templates?)",
    response_class=json_response_class,
)
async def deep_check(response: Response) -> List[str]:
    response.status_code = 200
    ret = list()
    for template in list(XDS_TEMPLATES["default"].keys()):
        try:
            req = mock_discovery_request("v3", template, expressions=["cluster=*"])
            cache.read(cache.client_id(req))
        # pylint: disable=broad-except
        except Exception as e:
            ret.append(f"Failed {template}: {str(e)}")
            response.status_code = 500
        else:
            ret.append(f"Rendered {template} OK")
    for attempt in range(5):
        try:
            worker_health = requests.get("http://localhost:9080/health")
            if worker_health.ok:
                return ret
        finally:
            await asyncio.sleep(attempt)
    response.status_code = 503
    ret.append("Worker unavailable")
    return ret


@router.get("/version", summary="Display the current version of Sovereign")
async def version_check() -> Response:
    return PlainTextResponse(f"Sovereign {__version__}")
