import json
from typing import Dict
import structlog
from structlog.exceptions import DropEvent
from structlog.threadlocal import (
    bind_threadlocal,
    clear_threadlocal,
    merge_threadlocal,
)
from contextvars import ContextVar
from sovereign import config

DEBUG = config.debug
APP_LOGS_ENABLED = config.logging.application_logs.enabled
ACCESS_LOGS_ENABLED = config.logging.access_logs.enabled
IGNORE_EMPTY = config.logging.access_logs.ignore_empty_fields
LOG_FMT = config.logging.access_logs.log_fmt

log_dictionary: ContextVar[dict] = ContextVar("log_dictionary", default=dict())
_configured_log_fmt = None

new_log_context = clear_threadlocal
add_log_context = bind_threadlocal


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


class AccessLogsEnabled:
    def __call__(self, logger, method_name, event_dict):
        if not ACCESS_LOGS_ENABLED:
            raise DropEvent
        return event_dict


class FilterDebugLogs:
    def __call__(self, logger, method_name, event_dict):
        if event_dict.get("level") == "debug" and not DEBUG:
            raise DropEvent
        return event_dict


def application_log(**kwargs) -> None:
    if APP_LOGS_ENABLED:
        _logger.msg(**kwargs)


def submit_log(ignore_empty=IGNORE_EMPTY) -> None:
    log = log_dictionary.get()
    formatted = format_log_fields(log, ignore_empty)
    _logger.msg(**formatted)
    clear_threadlocal()


def queue_log_fields(**kwargs) -> None:
    log = log_dictionary.get()
    log.update(kwargs)
    log_dictionary.set(log)


def configured_log_format(format=_configured_log_fmt) -> dict:
    if format is not None:
        return format
    if isinstance(LOG_FMT, str) and LOG_FMT != "":
        format = json.loads(LOG_FMT)
        return format
    return default_log_fmt()


def format_log_fields(log, ignore_empty) -> dict:
    formatted_dict = dict()
    for k, v in configured_log_format().items():
        try:
            value = v.format(**log)
        except KeyError:
            value = "-"
        if value in (None, "-") and ignore_empty:
            continue
        formatted_dict[k] = value
    return formatted_dict


structlog.configure(
    processors=[
        AccessLogsEnabled(),
        merge_threadlocal,
        structlog.stdlib.add_log_level,
        FilterDebugLogs(),
        structlog.processors.JSONRenderer(),
    ]
)
_logger = structlog.getLogger()
_configured_log_fmt = configured_log_format()
