import traceback
import uvicorn
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, FileResponse
from pkg_resources import resource_filename
from sovereign import config, asgi_config, __versionstr__, json_response_class
from sovereign.logs import add_log_context, LOG
from sovereign.sources import sources_refresh
from sovereign.views import crypto, discovery, healthchecks, admin, interface
from sovereign.middlewares import RequestContextLogMiddleware, LoggingMiddleware, get_request_id, \
    ScheduledTasksMiddleware

try:
    import sentry_sdk
    from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
except ImportError:  # pragma: no cover
    sentry_sdk = None
    SentryAsgiMiddleware = None


def generic_error_response(e):
    """
    Responds with a JSON object containing basic context
    about the exception passed in to this function.

    If the server is in debug mode, it will include a traceback in the response.

    The traceback is **always** emitted in logs.
    """
    error = {
        'error': e.__class__.__name__,
        'detail': getattr(e, 'detail', '-'),
        'request_id': get_request_id()
    }
    # Don't expose tracebacks in responses, but add it to the logs
    tb = [line for line in traceback.format_exc().split('\n')]
    add_log_context(**error, traceback=tb)
    if config.debug_enabled:
        error['traceback'] = tb
    return json_response_class(
        content=error,
        status_code=getattr(e, 'status_code', 500)
    )


def init_app() -> FastAPI:
    # Warm the sources once before starting
    sources_refresh()
    LOG.info('Initial fetch of Sources completed')

    application = FastAPI(
        title='Sovereign',
        version=__versionstr__,
        debug=config.debug_enabled
    )
    application.include_router(discovery.router, tags=['Configuration Discovery'])
    application.include_router(crypto.router, tags=['Cryptographic Utilities'], prefix='/crypto')
    application.include_router(admin.router, tags=['Debugging Endpoints'], prefix='/admin')
    application.include_router(interface.router, tags=['User Interface'], prefix='/ui')
    application.include_router(healthchecks.router, tags=['Healthchecks'])

    application.add_middleware(RequestContextLogMiddleware)
    application.add_middleware(LoggingMiddleware)
    application.add_middleware(ScheduledTasksMiddleware)

    if config.sentry_dsn and sentry_sdk:
        sentry_sdk.init(config.sentry_dsn)
        application.add_middleware(SentryAsgiMiddleware)
        LOG.info('Sentry middleware enabled')

    @application.exception_handler(500)
    async def exception_handler(_, exc: Exception) -> json_response_class:
        """
        We cannot incur the execution of this function from unit tests
        because the starlette test client simply returns exceptions and does
        not run them through the exception handler.
        Ergo, this is a facade function for `generic_error_response`
        """
        return generic_error_response(exc)  # pragma: no cover

    @application.get('/')
    def redirect_to_docs():
        return RedirectResponse('/ui')

    @application.get('/static/{filename}', summary='Return a static asset')
    def static(filename: str):
        return FileResponse(resource_filename('sovereign', f'static/{filename}'))

    return application


app = init_app()
LOG.info(f'Sovereign started and listening on {asgi_config.host}:{asgi_config.port}')


if __name__ == '__main__':  # pragma: no cover
    uvicorn.run(app, host='0.0.0.0', port=8000, access_log=False)
