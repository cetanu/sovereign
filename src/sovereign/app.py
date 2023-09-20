import asyncio
import traceback
import uvicorn
from collections import namedtuple
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, FileResponse, Response, JSONResponse
from sovereign import __version__
from sovereign.configuration import CONFIG, ASGI_CONFIG, POLLER, LOGS, TEMPLATE_CONTEXT
from sovereign.error_info import ErrorInfo
from sovereign.views import crypto, discovery, healthchecks, admin, interface
from sovereign.middlewares import (
    RequestContextLogMiddleware,
    LoggingMiddleware,
)
from sovereign.utils.resources import get_package_file
from sovereign.response_class import json_response_class

Router = namedtuple("Router", "module tags prefix")

DEBUG = CONFIG.debug
SENTRY_DSN = CONFIG.sentry_dsn.get_secret_value()


def generic_error_response(e: Exception) -> JSONResponse:
    """
    Responds with a JSON object containing basic context
    about the exception passed in to this function.

    If the server is in debug mode, it will include a traceback in the response.

    The traceback is **always** emitted in logs.
    """
    tb = [line for line in traceback.format_exc().split("\n")]
    info = ErrorInfo.from_exception(e)
    LOGS.access_logger.queue_log_fields(
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


app = FastAPI(
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
    app.include_router(router.module, tags=router.tags, prefix=router.prefix)

app.add_middleware(RequestContextLogMiddleware)
app.add_middleware(LoggingMiddleware)

try:
    if SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

        sentry_sdk.init(SENTRY_DSN)
        app.add_middleware(SentryAsgiMiddleware)
        LOGS.application_logger.logger.info("Sentry middleware enabled")
except ImportError:  # pragma: no cover
    pass


@app.exception_handler(500)
async def exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """
    We cannot incur the execution of this function from unit tests
    because the starlette test client simply returns exceptions and does
    not run them through the exception handler.
    Ergo, this is a facade function for `generic_error_response`
    """
    return generic_error_response(exc)  # pragma: no cover


@app.get("/")
async def redirect_to_docs() -> Response:
    return RedirectResponse("/ui")


@app.get("/static/{filename}", summary="Return a static asset")
async def static(filename: str) -> Response:
    return FileResponse(get_package_file("sovereign", f"static/{filename}"))  # type: ignore[arg-type]


@app.on_event("startup")
async def keep_sources_uptodate() -> None:
    asyncio.create_task(POLLER.poll_forever())


@app.on_event("startup")
async def refresh_template_context() -> None:
    asyncio.create_task(TEMPLATE_CONTEXT.start_refresh_context())


LOGS.application_logger.logger.info(
    f"Sovereign started and listening on {ASGI_CONFIG.host}:{ASGI_CONFIG.port}"
)


if __name__ == "__main__":  # pragma: no cover
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)
