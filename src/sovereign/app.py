import asyncio
import traceback
from collections import namedtuple

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, FileResponse, Response, JSONResponse

from sovereign import (
    __version__,
    config,
    asgi_config,
    json_response_class,
    poller,
    template_context,
    logs,
)
from sovereign.error_info import ErrorInfo
from sovereign.utils.resources import get_package_file
from sovereign.views import crypto, discovery, healthchecks, admin, interface
from sovereign.middlewares import (
    RequestContextLogMiddleware,
    LoggingMiddleware,
)

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
        Router(crypto.router, ["Cryptographic Utilities"], "/crypto"),
        Router(admin.router, ["Debugging Endpoints"], "/admin"),
        Router(interface.router, ["User Interface"], "/ui"),
        Router(healthchecks.router, ["Healthchecks"], ""),
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
        logs.application_logger.logger.info("Sentry middleware enabled")

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

    @application.on_event("startup")
    async def keep_sources_uptodate() -> None:
        asyncio.create_task(poller.poll_forever())

    @application.on_event("startup")
    async def refresh_template_context() -> None:
        asyncio.create_task(template_context.start_refresh_context())

    return application


app = init_app()
logs.application_logger.logger.info(
    f"Sovereign started and listening on {asgi_config.host}:{asgi_config.port}"
)


if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
