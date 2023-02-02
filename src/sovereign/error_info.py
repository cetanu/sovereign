import json

from typing import Union, Optional, Any
from dataclasses import dataclass, field, asdict
from functools import singledispatchmethod

from sovereign import get_request_id

try:
    BOTO = True
    from botocore.exceptions import ClientError
except ImportError:
    BOTO = False


StrKeyDict = dict[str, Any]
Detail = Union[str, StrKeyDict]


@dataclass
class ErrorInfo:
    error: str
    detail: Detail
    request_id: str = field(default_factory=get_request_id)
    traceback: Optional[list[str]] = None

    @classmethod
    def _get_error(cls, exc: Exception, detail: Detail) -> "ErrorInfo":
        return cls(exc.__class__.__name__, detail)

    @singledispatchmethod
    @classmethod
    def from_exception(cls, exc: Exception) -> "ErrorInfo":
        return cls._get_error(exc, getattr(exc, "detail", "-"))

    if BOTO:

        @from_exception.register
        @classmethod
        def _(cls, exc: ClientError) -> Any:
            detail = {
                "message": str(exc),
                "operation": exc.operation_name,
                "response": exc.response,
            }

            return cls._get_error(exc, detail)

    @property
    def detail_str(self) -> str:
        if isinstance(self.detail, str):
            return self.detail
        return json.dumps(self.detail)

    @property
    def response(self) -> StrKeyDict:
        data = asdict(self)

        if data["traceback"] is None:
            del data["traceback"]

        return data
