from functools import cached_property
from typing import Any, Dict

import structlog
from structlog.stdlib import BoundLogger

from sovereign.logging.base_logger import BaseLogger
from sovereign.logging.types import EventDict, LoggingType, ProcessedMessage
from sovereign.schemas import SovereignConfigv2


class ApplicationLogger(BaseLogger):
    def __init__(self, root_logger: BoundLogger, config: SovereignConfigv2):
        self._application_logs_enabled = config.logging.application_logs.enabled
        self._user_log_fmt = config.logging.application_logs.log_fmt

        self.logger: BoundLogger = structlog.wrap_logger(
            root_logger,
            wrapper_class=structlog.BoundLogger,
            processors=[
                self.is_enabled_processor,
                self.merge_in_threadlocal,
                self.format_application_log_fields,
            ],
            type=LoggingType.APPLICATION,
        )

    @cached_property
    def is_enabled(self) -> bool:
        return self._application_logs_enabled

    @cached_property
    def _default_log_fmt(self) -> Dict[str, str]:
        return {
            "type": "{type}",
            "event": "{event}",
            "error": "{error}",
            "traceback": "{traceback}",
            "last_update": "{last_update}",
            "instance_count": "{instance_count}",
        }

    def format_application_log_fields(
        self, logger: BoundLogger, method_name: str, event_dict: EventDict
    ) -> ProcessedMessage:
        formatted_dict: Dict[str, Any] = {
            "level": method_name,
        }
        for k, v in self.get_configured_log_format.items():
            try:
                value: str = v.format(**event_dict)
            except KeyError:
                continue
            formatted_dict[k] = value
        return formatted_dict
