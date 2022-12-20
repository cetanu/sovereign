import json
import threading
from typing import Dict, Any, Optional, Tuple, Mapping, MutableMapping, Union

import structlog
from structlog.exceptions import DropEvent

from sovereign.schemas import SovereignConfigv2


LOG_QUEUE = threading.local()


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


_configured_log_fmt: Optional[Dict[str, str]] = None

EventDict = MutableMapping[str, Any]
ProcessedMessage = Union[Mapping[str, Any], str, bytes, Tuple[Any, ...]]


class LoggerBootstrapper:
    def __init__(self, config: SovereignConfigv2) -> None:
        self.debug = config.debug
        self.app_logs_enabled = config.logging.application_logs.enabled
        self.access_logs_enabled = config.logging.access_logs.enabled
        self.ignore_empty = config.logging.access_logs.ignore_empty_fields
        self.log_fmt = config.logging.access_logs.log_fmt
        self.logger = self.bootstrap()

    def bootstrap(self) -> Any:
        structlog.configure(
            processors=[
                self.access_logs_enabled_processor,
                self.debug_logs_processor,
                self.merge_in_threadlocal,
                self.format_log_fields,
                structlog.processors.JSONRenderer(),
            ]
        )
        logger = structlog.getLogger()
        self.configured_log_fmt = self.configured_log_format()
        return logger

    def access_logs_enabled_processor(
        self, logger: Any, method_name: str, event_dict: EventDict
    ) -> ProcessedMessage:
        if not self.access_logs_enabled:
            raise DropEvent
        return event_dict

    def debug_logs_processor(
        self, logger: Any, method_name: str, event_dict: EventDict
    ) -> ProcessedMessage:
        if event_dict.get("level") == "debug" and not self.debug:
            raise DropEvent
        return event_dict

    def application_log(self, **kwargs: Any) -> None:
        if self.app_logs_enabled:
            self.logger.msg(**kwargs)

    def merge_in_threadlocal(
        self, logger: Any, method_name: str, event_dict: EventDict
    ) -> ProcessedMessage:
        self._ensure_threadlocal()
        fields: Dict[str, Any] = LOG_QUEUE.fields.copy()
        fields.update(event_dict)
        return fields

    def clear_log_fields(self) -> None:
        LOG_QUEUE.fields = dict()

    def _ensure_threadlocal(self) -> None:
        if not hasattr(LOG_QUEUE, "fields"):
            LOG_QUEUE.fields = dict()

    def queue_log_fields(self, **kwargs: Any) -> None:
        self._ensure_threadlocal()
        LOG_QUEUE.fields.update(kwargs)

    def configured_log_format(
        self, format: Optional[Dict[str, str]] = _configured_log_fmt
    ) -> Dict[str, str]:
        if format is not None:
            return format
        if isinstance(self.log_fmt, str) and self.log_fmt != "":
            format = json.loads(self.log_fmt)
            if not isinstance(format, dict):
                raise RuntimeError(
                    f"Failed to parse log format as JSON: {self.log_fmt}"
                )
            return format
        return default_log_fmt()

    def format_log_fields(
        self, logger: Any, method_name: str, event_dict: EventDict
    ) -> ProcessedMessage:
        formatted_dict: Dict[str, Any] = dict()
        for k, v in self.configured_log_format().items():
            try:
                value: str = v.format(**event_dict)
            except KeyError:
                value = "-"
            if value in (None, "-") and self.ignore_empty:
                continue
            formatted_dict[k] = value
        return formatted_dict
