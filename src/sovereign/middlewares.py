import os
import time
import schedule
from uuid import uuid4
from contextvars import ContextVar
from fastapi.requests import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from sovereign import config
from sovereign.statistics import stats
from sovereign.logs import LOG, add_log_context, new_log_context

_request_id_ctx_var: ContextVar[str] = ContextVar('request_id', default=None)


def get_request_id() -> str:
    return _request_id_ctx_var.get()


class RequestContextLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        response = Response("Internal server error", status_code=500)
        token = _request_id_ctx_var.set(str(uuid4()))
        try:
            response: Response = await call_next(request)
        finally:
            response.headers['X-Request-ID'] = get_request_id()
            _request_id_ctx_var.reset(token)
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        start_time = time.time()
        response = Response("Internal server error", status_code=500)
        new_log_context()
        add_log_context(
            env=config.environment,
            site=request.headers.get('host', '-'),
            method=request.method,
            uri_path=request.url.path,
            uri_query=dict(request.query_params.items()),
            src_ip=request.client.host,
            src_port=request.client.port,
            pid=os.getpid(),
            user_agent=request.headers.get('user-agent', '-'),
            bytes_in=request.headers.get('content-length', '-')
        )
        try:
            response: Response = await call_next(request)
        finally:
            duration = time.time() - start_time
            LOG.info(
                bytes_out=response.headers.get('content-length', '-'),
                status=response.status_code,
                duration=duration,
                request_id=response.headers.get('X-Request-Id', '-')
            )
            if 'discovery' in str(request.url):
                tags = {
                    'path': request.url.path,
                    'xds_type': response.headers.get("X-Sovereign-Requested-Type"),
                    'client_version': response.headers.get("X-Sovereign-Client-Build"),
                    'response_code': response.status_code,
                }
                tags = [
                    ':'.join(map(str, [k, v]))
                    for k, v in tags.items()
                    if v is not None
                ]
                stats.increment('discovery.rq_total', tags=tags)
                stats.timing('discovery.rq_ms', value=duration * 1000, tags=tags)
        return response


class ScheduledTasksMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        response = Response("Internal server error", status_code=500)
        try:
            response: Response = await call_next(request)
        finally:
            schedule.run_pending()
        return response
