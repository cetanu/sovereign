import os
import re
import time
from uuid import uuid4
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from sovereign import config
from sovereign.statistics import stats
from sovereign.logs import LOG

url_path = re.compile(r'^(?P<scheme>https?|wss)://(?P<host>[^/]+)')

_request_id_ctx_var: ContextVar[str] = ContextVar('request_id', default=None)
_request_logger_ctx_var = ContextVar('logger', default=None)


def add_log_context(**kwargs):
    logger = _request_logger_ctx_var.get()
    if logger is None:
        # do smth
        pass
    logger = logger.bind(**kwargs)
    _request_logger_ctx_var.set(logger)


def get_request_id() -> str:
    return _request_id_ctx_var.get()


class RequestContextLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        request_id = _request_id_ctx_var.set(str(uuid4()))
        response = await call_next(request)
        response.headers['X-Request-ID'] = get_request_id()
        _request_id_ctx_var.reset(request_id)
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint):
        start_time = time.time()
        response = Response("Internal server error", status_code=500)

        log = LOG.bind(
            uri_path=url_path.sub('', request.url.path),
            uri_query=dict(request.query_params.items()),
            src_ip=request.client.host,
            src_port=request.client.port,
            site=request.headers.get('host', '-'),
            method=request.method,
            user_agent=request.headers.get('user-agent', '-'),
            env=config.environment,
            pid=os.getpid(),
            request_id=get_request_id(),
            bytes_in=request.headers.get('content-length', '-')
        )
        _request_logger_ctx_var.set(log)
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
                stats.timing('rq_ms', value=duration * 1000, tags=tags)
        return response
