import json
import threading
import structlog
from typing import Dict, Any, TypeVar, Optional, cast
from structlog.exceptions import DropEvent
from sovereign import config

DEBUG = config.debug
APP_LOGS_ENABLED = config.logging.application_logs.enabled
ACCESS_LOGS_ENABLED = config.logging.access_logs.enabled
IGNORE_EMPTY = config.logging.access_logs.ignore_empty_fields
LOG_FMT = config.logging.access_logs.log_fmt

LOG_QUEUE = threading.local()
_configured_log_fmt: Optional[Dict[str, str]] = None


def default_log_fmt() -> Dict[str, str]:
    return {
        "env": "{ENVIRONMENT}",
        "site": "{HOST}",
        "method": "{METHOD}",
        "uri_path": "{PATH}",
        "uri_query": "{QUERY}",
        "src_ip": "{SOURCE_IP}",
        "src_port": "{SOURCE_PORT}",
        "pid": "{PID}",
        "user_agent": "{USER_AGENT}",
        "bytes_in": "{BYTES_RX}",
        "bytes_out": "{BYTES_TX}",
        "status": "{STATUS_CODE}",
        "duration": "{DURATION}",
        "request_id": "{REQUEST_ID}",
        "resource_version": "{XDS_CLIENT_VERSION} -> {XDS_SERVER_VERSION}",
        "resource_names": "{XDS_RESOURCES}",
        "envoy_ver": "{XDS_ENVOY_VERSION}",
        "traceback": "{TRACEBACK}",
        "error": "{ERROR}",
        "detail": "{ERROR_DETAIL}",
    }


T = TypeVar("T", bound=Dict[str, Any])


class AccessLogsEnabled:
    def __call__(self, logger: Any, method_name: str, event_dict: T) -> T:
        if not ACCESS_LOGS_ENABLED:
            raise DropEvent
        return event_dict


class FilterDebugLogs:
    def __call__(self, logger: Any, method_name: str, event_dict: T) -> T:
        if event_dict.get("level") == "debug" and not DEBUG:
            raise DropEvent
        return event_dict


def application_log(**kwargs: Any) -> None:
    if APP_LOGS_ENABLED:
        logger.msg(**kwargs)


def merge_in_threadlocal(logger: Any, method_name: str, event_dict: T) -> T:
    _ensure_threadlocal()
    fields = LOG_QUEUE.fields.copy()
    fields.update(event_dict)
    return cast(T, fields)


def clear_log_fields() -> None:
    LOG_QUEUE.fields = dict()


def _ensure_threadlocal() -> None:
    if not hasattr(LOG_QUEUE, "fields"):
        LOG_QUEUE.fields = dict()


def queue_log_fields(**kwargs: Any) -> None:
    _ensure_threadlocal()
    LOG_QUEUE.fields.update(kwargs)


def configured_log_format(
    format: Optional[Dict[str, str]] = _configured_log_fmt
) -> Dict[str, str]:
    if format is not None:
        return format
    if isinstance(LOG_FMT, str) and LOG_FMT != "":
        format = json.loads(LOG_FMT)
        if not isinstance(format, dict):
            raise RuntimeError(f"Failed to parse log format as JSON: {LOG_FMT}")
        return format
    return default_log_fmt()


def format_log_fields(logger: Any, method_name: str, event_dict: T) -> T:
    formatted_dict: Dict[str, Any] = dict()
    for k, v in configured_log_format().items():
        try:
            value: str = v.format(**event_dict)
        except KeyError:
            value = "-"
        if value in (None, "-") and IGNORE_EMPTY:
            continue
        formatted_dict[k] = value
    return cast(T, formatted_dict)


structlog.configure(
    processors=[
        AccessLogsEnabled(),
        FilterDebugLogs(),
        merge_in_threadlocal,
        format_log_fields,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.getLogger()
_configured_log_fmt = configured_log_format()
