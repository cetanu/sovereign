import os
import time
import traceback
import uvicorn
from uuid import uuid4
from datetime import datetime, timedelta, date
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response, RedirectResponse, JSONResponse
from sovereign import statsd, config, __versionstr__
from sovereign.sources import refresh
from sovereign.logs import LOG
from sovereign.views import (
    crypto,
    discovery,
    healthchecks,
    admin,
)

try:
    import sentry_sdk
    from sentry_asgi import SentryMiddleware
except ImportError:
    sentry_sdk = None
    SentryMiddleware = None


def init_app():
    # Warm the sources once before starting
    refresh()

    application = FastAPI(
        title='Sovereign',
        version=__versionstr__
    )
    application.include_router(discovery.router)

    @application.middleware('http')
    async def logging_middleware(request: Request, call_next):
        start_time = time.time()
        response = Response("Internal server error", status_code=500)

        log = LOG.bind(
            uri_path=request.url.path,
            uri_query=dict(request.query_params.items()),
            src_ip=request.client.host,
            src_port=request.client.port,
            site=request.headers.get('host', '-'),
            method=request.method,
            user_agent=request.headers.get('user-agent', '-'),
            env=config.environment,
            pid=os.getpid(),
            request_id=str(uuid4()),
            start_time=start_time,
            bytes_in=request.headers.get('content-length', '-')
        )
        try:
            response: Response = await call_next(request)
        finally:
            duration = time.time() - start_time
            log.msg(
                duration=duration,
                status=response.status_code,
                bytes_out=response.headers.get('content-length', '-'),
            )
            if 'discovery' in str(request.url):
                tags = [
                    f'path:{request.url}',
                    f'code:{response.status_code}',
                ]
                statsd.timing('rq_ms', value=duration, tags=tags)
        return response

    @application.get('/')
    async def index():
        return RedirectResponse('/admin/xds_dump')

    @application.exception_handler(Exception)
    async def exception_handler(request: Request, exc: Exception):
        error = {
            'error': exc.__class__.__name__,
        }

        # Add the description from Quart exception classes
        if hasattr(exc, 'description') or hasattr(exc, 'status'):
            error['description'] = getattr(exc.status, 'description', exc.description)

        if config.debug_enabled:
            error['traceback'] = [line for line in traceback.format_exc().split('\n')]
        status_code = getattr(exc, 'status', getattr(exc, 'code', 500))
        return JSONResponse(content=error, status_code=status_code)

    # if config.sentry_dsn and sentry_sdk:
    #     sentry_sdk.init(config.sentry_dsn)
    #     # noinspection PyTypeChecker
    #     application = SentryMiddleware(application)

    return application


app = init_app()


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
