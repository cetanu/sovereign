import asyncio

import pydantic
import requests
from fastapi import Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.routing import APIRouter
from typing_extensions import Annotated, Literal

from sovereign import __version__
from sovereign.configuration import XDS_TEMPLATES, config
from sovereign.response_class import json_response_class
from sovereign.utils.mock import mock_discovery_request
from sovereign.v2.web import wait_for_discovery_response
from sovereign.views import reader

router = APIRouter()

State = Literal["FAIL"] | Literal["OK"]
Message = str
CheckResult = tuple[State, Message] | State


class DeepCheckResult(pydantic.BaseModel):
    templates: dict[str, CheckResult] = pydantic.Field(default_factory=dict)
    worker: CheckResult = pydantic.Field(default=("FAIL", "Worker unavailable"))

    def response(self) -> PlainTextResponse:
        return PlainTextResponse(content=self.message, status_code=self.status)

    def json_response(self) -> JSONResponse:
        return json_response_class(content=self.model_dump(), status_code=self.status)

    @property
    def message(self) -> str:
        msg = "Templates:\n"
        for template, result in sorted(self.templates.items()):
            msg += f"* {template} {result}\n"
        msg += f"Worker: {self.worker}\n"
        return msg

    @property
    def status(self) -> int:
        if self.is_err():
            return 500
        return 200

    def is_err(self):
        for result in self.templates.values():
            if result[0] == "FAIL":
                return True
        if self.worker[0] == "FAIL":
            return True
        return False


@router.get("/healthcheck", summary="Healthcheck (Does the server respond to HTTP?)")
async def health_check() -> Response:
    return PlainTextResponse("OK", status_code=200)


@router.get(
    "/deepcheck",
    summary="Deepcheck (Can the server render all default templates?)",
)
async def deep_check(
    request: Request,
    worker_attempts: Annotated[
        int,
        Query(
            description="How many times to try to contact the worker before giving up",
        ),
    ] = 5,
    envoy_service_cluster: Annotated[
        str,
        Query(
            description="Which service cluster to use when checking if a template can be rendered",
        ),
    ] = "*",
) -> Response:
    result = DeepCheckResult()
    for template in list(XDS_TEMPLATES["default"].keys()):
        discovery_request = mock_discovery_request(
            "v3",
            template,
            expressions=[f"cluster={envoy_service_cluster}"],
        )

        if config.worker_v2_enabled:
            # we're set up to use v2 of the worker
            response = await wait_for_discovery_response(discovery_request)
            if response:
                result.templates[template] = "OK"
            else:
                result.templates[template] = (
                    "FAIL",
                    f"Failed to render {template}",
                )

            result.worker = "OK"
        else:
            try:
                _ = await reader.blocking_read(discovery_request)  # ty: ignore[possibly-missing-attribute]
                result.templates[template] = "OK"
            except Exception as e:
                result.templates[template] = ("FAIL", f"Failed {template}: {str(e)}")

    if not config.worker_v2_enabled:
        for attempt in range(worker_attempts):
            try:
                worker_health = requests.get("http://localhost:9080/health")
                if worker_health.ok:
                    result.worker = "OK"
                    break
            except Exception as e:
                result.worker = ("FAIL", str(e))
                await asyncio.sleep(attempt)

    if "json" in request.headers.get("Accept", ""):
        return result.json_response()

    return result.response()


@router.get("/version", summary="Display the current version of Sovereign")
async def version_check() -> Response:
    return PlainTextResponse(f"Sovereign {__version__}")
