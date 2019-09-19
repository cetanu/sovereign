import traceback
import uvicorn
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from sovereign import config, __versionstr__
from sovereign.sources import sources_refresh
from sovereign.views import crypto, discovery, healthchecks, admin, interface
from sovereign.middlewares import RequestContextLogMiddleware, get_request_id, LoggingMiddleware

try:
    import sentry_sdk
    from sentry_asgi import SentryMiddleware
except ImportError:
    sentry_sdk = None
    SentryMiddleware = None


def init_app() -> FastAPI:
    # Warm the sources once before starting
    sources_refresh()

    application = FastAPI(
        title='Sovereign',
        version=__versionstr__,
        debug=config.debug_enabled
    )
    application.include_router(discovery.router, tags=['Configuration Discovery'], prefix='/v2')
    application.include_router(crypto.router, tags=['Cryptographic Utilities'], prefix='/crypto')
    application.include_router(admin.router, tags=['Debugging Endpoints'], prefix='/admin')
    application.include_router(interface.router, tags=['User Interface'], prefix='/ui')
    application.include_router(healthchecks.router, tags=['Healthchecks'])

    application.add_middleware(RequestContextLogMiddleware)
    application.add_middleware(LoggingMiddleware)

    if config.sentry_dsn and sentry_sdk:
        sentry_sdk.init(config.sentry_dsn)
        # noinspection PyTypeChecker
        application.add_middleware(SentryMiddleware)

    @application.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception):
        error = {
            'error': exc.__class__.__name__,
            'request_id': get_request_id()
        }

        # Add the description from Quart exception classes
        if hasattr(exc, 'detail'):
            error['description'] = getattr(exc.detail, 'description', 'unknown')

        if config.debug_enabled:
            error['traceback'] = [line for line in traceback.format_exc().split('\n')]
        status_code = getattr(exc, 'status_code', getattr(exc, 'code', 500))
        return JSONResponse(content=error, status_code=status_code)

    @application.get('/')
    def redirect_to_docs():
        return RedirectResponse('/docs')

    return application


app = init_app()


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000, access_log=False)
