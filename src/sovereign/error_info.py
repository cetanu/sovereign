import json

from typing import Union, Optional
from dataclasses import dataclass, field, asdict
from functools import singledispatchmethod

from sovereign import get_request_id

try:
    BOTO = True
    from botocore.exceptions import ClientError
except ImportError:
    BOTO = False


@dataclass
class ErrorInfo:
    error: str
    detail: Union[str, dict]
    request_id: str = field(default_factory=get_request_id)
    traceback: Optional[list] = None

    @classmethod
    def _get_error(cls, exc: Exception, detail: Union[str, dict]):
        return cls(exc.__class__.__name__, detail)

    @singledispatchmethod
    @classmethod
    def from_exception(cls, exc):
        return cls._get_error(exc, getattr(exc, "detail", "-"))

    if BOTO:

        @from_exception.register
        @classmethod
        def _(cls, exc: ClientError):
            detail = {
                "message": str(exc),
                "operation": exc.operation_name,
                "response": exc.response,
            }

            return cls._get_error(exc, detail)

    @property
    def detail_str(self):
        if isinstance(self.detail, str):
            return self.detail
        return json.dumps(self.detail)

    @property
    def response(self):
        data = asdict(self)

        if data["traceback"] is None:
            del data["traceback"]

        return data
