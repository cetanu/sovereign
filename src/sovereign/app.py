import traceback
from collections import namedtuple

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from starlette_context.middleware import RawContextMiddleware

from sovereign import (
    __version__,
    config,
    logs,
)
from sovereign.schemas import DiscoveryTypes
from sovereign.response_class import json_response_class
from sovereign.error_info import ErrorInfo
from sovereign.middlewares import LoggingMiddleware, RequestContextLogMiddleware
from sovereign.utils.resources import get_package_file
from sovereign.views import crypto, discovery, healthchecks, interface, api

Router = namedtuple("Router", "module tags prefix")

DEBUG = config.debug
SENTRY_DSN = config.sentry_dsn.get_secret_value()

try:
    import sentry_sdk
    from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

    SENTRY_INSTALLED = True
except ImportError:  # pragma: no cover
    SENTRY_INSTALLED = False


def generic_error_response(e: Exception) -> JSONResponse:
    """
    Responds with a JSON object containing basic context
    about the exception passed in to this function.

    If the server is in debug mode, it will include a traceback in the response.

    The traceback is **always** emitted in logs.
    """
    tb = [line for line in traceback.format_exc().split("\n")]
    info = ErrorInfo.from_exception(e)
    logs.access_logger.queue_log_fields(
        ERROR=info.error,
        ERROR_DETAIL=info.detail,
        TRACEBACK=tb,
    )
    # Don't expose tracebacks in responses, but add it to the logs
    if DEBUG:
        info.traceback = tb
    return json_response_class(
        content=info.response, status_code=getattr(e, "status_code", 500)
    )


def init_app() -> FastAPI:
    application = FastAPI(
        title="Sovereign",
        version=__version__,
        debug=DEBUG,
        default_response_class=json_response_class,
    )

    routers = (
        Router(discovery.router, ["Configuration Discovery"], ""),
        Router(api.router, ["API"], "/api"),
        Router(healthchecks.router, ["Healthchecks"], ""),
        Router(interface.router, ["User Interface"], "/ui"),
        Router(crypto.router, ["Cryptographic Utilities"], "/crypto"),
    )
    for router in routers:
        application.include_router(
            router.module, tags=router.tags, prefix=router.prefix
        )

    application.add_middleware(RequestContextLogMiddleware)
    application.add_middleware(LoggingMiddleware)

    if SENTRY_INSTALLED and SENTRY_DSN:
        sentry_sdk.init(SENTRY_DSN)
        application.add_middleware(SentryAsgiMiddleware)

    application.add_middleware(RawContextMiddleware)

    @application.exception_handler(500)
    async def exception_handler(_: Request, exc: Exception) -> JSONResponse:
        """
        We cannot incur the execution of this function from unit tests
        because the starlette test client simply returns exceptions and does
        not run them through the exception handler.
        Ergo, this is a facade function for `generic_error_response`
        """
        return generic_error_response(exc)  # pragma: no cover

    @application.get("/")
    async def redirect_to_docs() -> Response:
        return RedirectResponse("/ui")

    @application.get("/static/{filename}", summary="Return a static asset")
    async def static(filename: str) -> Response:
        return FileResponse(get_package_file("sovereign", f"static/{filename}"))  # type: ignore[arg-type]

    @application.get(
        "/admin/xds_dump",
        summary="Deprecated API, please use /api/resources/{resource_type}",
    )
    async def dump_resources(request: Request) -> Response:
        resource_type = DiscoveryTypes(request.query_params.get("xds_type", "cluster"))
        resource_name = request.query_params.get("name")
        api_version = request.query_params.get("api_version", "v3")
        service_cluster = request.query_params.get("service_cluster", "*")
        region = request.query_params.get("region")
        version = request.query_params.get("version")
        response = await api.resource(
            resource_type=resource_type,
            resource_name=resource_name,
            api_version=api_version,
            service_cluster=service_cluster,
            region=region,
            version=version,
        )
        response.headers["Deprecation"] = "true"
        response.headers["Link"] = f'</api/resources/{resource_type}>; rel="alternate"'
        response.headers["Warning"] = (
            f'299 - "Deprecated API: please use /api/resources/{resource_type}"'
        )
        response.status_code = 299
        return response

    return application


app = init_app()


if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
