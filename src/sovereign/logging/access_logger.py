from functools import cached_property
from typing import Any, Dict

import structlog
from structlog.stdlib import BoundLogger

from sovereign.logging.base_logger import BaseLogger
from sovereign.logging.types import EventDict, LoggingType, ProcessedMessage
from sovereign.schemas import SovereignConfigv2


class AccessLogger(BaseLogger):
    def __init__(self, root_logger: BoundLogger, config: SovereignConfigv2):
        self._access_logs_enabled = config.logging.access_logs.enabled
        self._ignore_empty = config.logging.access_logs.ignore_empty_fields
        self._user_log_fmt = config.logging.access_logs.log_fmt

        self.logger: BoundLogger = structlog.wrap_logger(
            root_logger,
            wrapper_class=structlog.BoundLogger,
            processors=[
                self.is_enabled_processor,
                self.merge_in_threadlocal,
                self.format_access_log_fields,
            ],
            type=LoggingType.ACCESS,
        )

    @cached_property
    def is_enabled(self) -> bool:
        return self._access_logs_enabled

    @cached_property
    def _default_log_fmt(self) -> Dict[str, str]:
        return {
            "type": "{type}",
            "event": "{event}",
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

    def format_access_log_fields(
        self, logger: BoundLogger, method_name: str, event_dict: EventDict
    ) -> ProcessedMessage:
        formatted_dict: Dict[str, Any] = dict()
        for k, v in self.get_configured_log_format.items():
            try:
                value: str = v.format(**event_dict)
            except KeyError:
                value = "-"
            if value in (None, "-") and self._ignore_empty:
                continue
            formatted_dict[k] = value
        return formatted_dict
