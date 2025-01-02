import json
from abc import ABC, abstractmethod
from functools import cached_property
from typing import Dict, Optional

from structlog.exceptions import DropEvent
from structlog.stdlib import BoundLogger

from sovereign.logging.types import EventDict, ProcessedMessage


class BaseLogger(ABC):
    _user_log_fmt: Optional[str]

    @property
    @abstractmethod
    def is_enabled(self) -> bool: ...

    @property
    @abstractmethod
    def _default_log_fmt(self) -> Dict[str, str]: ...

    def is_enabled_processor(
        self, logger: BoundLogger, method_name: str, event_dict: EventDict
    ) -> ProcessedMessage:
        if not self.is_enabled:
            raise DropEvent
        return event_dict

    @cached_property
    def get_configured_log_format(self) -> Dict[str, str]:
        if isinstance(self._user_log_fmt, str) and self._user_log_fmt != "":
            format = json.loads(self._user_log_fmt)
            if not isinstance(format, dict):
                raise RuntimeError(
                    f"Failed to parse log format as JSON: {self._user_log_fmt}"
                )
            if "event" not in format:
                format["event"] = "{event}"
            return format
        return self._default_log_fmt
