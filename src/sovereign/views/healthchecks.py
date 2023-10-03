from typing import List
from fastapi import Response
from fastapi.routing import APIRouter
from fastapi.responses import PlainTextResponse
from sovereign import XDS_TEMPLATES, __version__, json_response_class
from sovereign.utils.mock import mock_discovery_request
from sovereign.views.discovery import perform_discovery


router = APIRouter()


@router.get("/healthcheck", summary="Healthcheck (Does the server respond to HTTP?)")
async def health_check() -> Response:
    return PlainTextResponse("OK")


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
            req = mock_discovery_request(service_cluster="*")
            await perform_discovery(req, "v3", resource_type=template, skip_auth=True)
        # pylint: disable=broad-except
        except Exception as e:
            ret.append(f"Failed {template}: {str(e)}")
        else:
            ret.append(f"Rendered {template} OK")
    return ret


@router.get("/version", summary="Display the current version of Sovereign")
async def version_check() -> Response:
    return PlainTextResponse(f"Sovereign {__version__}")
