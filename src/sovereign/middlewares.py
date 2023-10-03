import os
import time
from uuid import uuid4
from fastapi.requests import Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from sovereign import config, logs, get_request_id, _request_id_ctx_var, stats


class RequestContextLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = Response("Internal server error", status_code=500)
        token = _request_id_ctx_var.set(str(uuid4()))
        try:
            response = await call_next(request)
        finally:
            req_id = get_request_id()
            response.headers["X-Request-ID"] = req_id
            logs.access_logger.queue_log_fields(REQUEST_ID=req_id)
            _request_id_ctx_var.reset(token)
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.time()
        response = Response("Internal server error", status_code=500)

        source_ip, source_port = "0.0.0.0", 0
        if addr := request.client:
            source_ip = addr.host
            source_port = addr.port
        if xff := request.headers.get("X-Forwarded-For"):
            source_ip = xff.split(",")[0]  # leftmost address
        logs.access_logger.clear_log_fields()
        logs.access_logger.queue_log_fields(
            ENVIRONMENT=config.legacy_fields.environment,
            HOST=request.headers.get("host", "-"),
            METHOD=request.method,
            PATH=request.url.path,
            QUERY=dict(request.query_params.items()),
            SOURCE_IP=source_ip,
            SOURCE_PORT=source_port,
            PID=os.getpid(),
            USER_AGENT=request.headers.get("user-agent", "-"),
            BYTES_RX=request.headers.get("content-length", "-"),
        )
        try:
            response = await call_next(request)
        finally:
            duration = time.time() - start_time
            logs.access_logger.queue_log_fields(
                BYTES_TX=response.headers.get("content-length", "-"),
                STATUS_CODE=response.status_code,
                DURATION=duration,
            )
            if "discovery" in str(request.url):
                request_info = {
                    "path": request.url.path,
                    "xds_type": response.headers.get("X-Sovereign-Requested-Type"),
                    "client_version": response.headers.get("X-Sovereign-Client-Build"),
                    "response_code": response.status_code,
                }
                tags = [
                    ":".join(map(str, [k, v]))
                    for k, v in request_info.items()
                    if v is not None
                ]
                stats.increment("discovery.rq_total", tags=tags)
                stats.timing("discovery.rq_ms", value=duration * 1000, tags=tags)
            logs.access_logger.logger.info("request")
        return response
