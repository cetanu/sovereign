from typing import Type
from importlib.util import find_spec
from fastapi.responses import JSONResponse


json_response_class: Type[JSONResponse] = JSONResponse
if find_spec("orjson"):
    from fastapi.responses import ORJSONResponse

    json_response_class = ORJSONResponse

elif find_spec("ujson"):
    from fastapi.responses import UJSONResponse

    json_response_class = UJSONResponse


__all__ = ["json_response_class"]
