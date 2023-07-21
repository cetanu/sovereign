from enum import StrEnum
from typing import Any, Mapping, MutableMapping, Tuple, Union

EventDict = MutableMapping[str, Any]
ProcessedMessage = Union[Mapping[str, Any], str, bytes, Tuple[Any, ...]]


class LoggingType(StrEnum):
    ACCESS = "access"
    APPLICATION = "application"
