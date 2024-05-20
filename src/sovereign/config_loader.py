import os
import json
from enum import Enum
from typing import Any, Dict, Callable, Union, Protocol
from types import ModuleType
import yaml
import jinja2
import requests
import importlib
from importlib.machinery import SourceFileLoader
from pathlib import Path
from pydantic import BaseModel
from sovereign.utils.resources import get_package_file_bytes


class Serialization(Enum):
    """
    Types of deserialization available in Sovereign
    for loading configuration field values.
    """

    yaml = "yaml"
    json = "json"
    orjson = "orjson"
    ujson = "ujson"
    jinja = "jinja"
    jinja2 = "jinja2"
    string = "string"
    raw = "raw"
    skip = "skip"


jinja_env = jinja2.Environment(autoescape=True)


def passthrough(item: Any) -> Any:
    return item


def string(item: Any) -> Any:
    return str(item)


serializers: Dict[Serialization, Callable[[Any], Any]] = {
    Serialization.yaml: yaml.safe_load,
    Serialization.json: json.loads,
    Serialization.jinja: jinja_env.from_string,
    Serialization.jinja2: jinja_env.from_string,
    Serialization.string: string,
    Serialization.raw: passthrough,
}


try:
    import ujson

    serializers[Serialization.ujson] = ujson.loads
    jinja_env.policies["json.dumps_function"] = ujson.dumps
except ImportError:
    # This lambda will raise an exception when the serializer is used; otherwise we should not crash
    serializers[Serialization.ujson] = lambda *a, **kw: raise_(
        ImportError("ujson must be installed to use in config_loaders")
    )

try:
    import orjson

    serializers[Serialization.orjson] = orjson.loads

    # orjson.dumps returns bytes, so we have to wrap & decode it
    def orjson_dumps(*args: Any, **kwargs: Any) -> Any:
        try:
            representation = orjson.dumps(*args, **kwargs)
        except TypeError:
            raise TypeError(f"Unable to dump objects using ORJSON: {args}, {kwargs}")
        try:
            return representation.decode()
        except Exception as e:
            raise e.__class__(
                f"Unable to decode ORJSON: {representation!r}. Original exception: {e}"
            )

    jinja_env.policies["json.dumps_function"] = orjson_dumps
    jinja_env.policies["json.dumps_kwargs"] = {"option": orjson.OPT_SORT_KEYS}
except ImportError:
    # This lambda will raise an exception when the serializer is used; otherwise we should not crash
    serializers[Serialization.orjson] = lambda *a, **kw: raise_(
        ImportError("orjson must be installed to use in config_loaders")
    )

try:
    import boto3
except ImportError:
    boto3 = None


class CustomLoader(Protocol):
    def load(self, path: str, ser: Serialization) -> Any:
        ...


class Loadable(BaseModel):
    protocol: str = "http"
    serialization: Serialization = Serialization.yaml
    path: str

    def load(self, default: Any = None) -> Any:
        try:
            return loaders[self.protocol](self.path, self.serialization)
        except Exception:
            if default is not None:
                return default
            raise

    @staticmethod
    def from_legacy_fmt(fmt_string: str) -> "Loadable":
        if "://" not in fmt_string:
            return Loadable(
                protocol="inline", serialization=Serialization.string, path=fmt_string
            )
        try:
            scheme, path = fmt_string.split("://")
        except ValueError:
            raise ValueError(fmt_string)
        try:
            proto, ser = scheme.split("+")
        except ValueError:
            proto, ser = scheme, "yaml"

        serialization: Serialization = Serialization(ser)
        if proto in ("python", "module"):
            serialization = Serialization.raw
        if proto in ("http", "https"):
            path = "://".join([proto, path])

        return Loadable(
            protocol=proto,
            serialization=serialization,
            path=path,
        )


def raise_(e: Exception) -> Exception:
    raise e


def load_file(path: str, ser: Serialization) -> Any:
    with open(path) as f:
        contents = f.read()
        try:
            return serializers[ser](contents)
        except FileNotFoundError:
            raise FileNotFoundError(f"Unable to load {path}")


def load_package_data(path: str, ser: Serialization) -> Any:
    pkg, pkg_file = path.split(":")
    data = get_package_file_bytes(pkg, pkg_file)
    return serializers[ser](data)


def load_http(path: str, ser: Serialization) -> Any:
    response = requests.get(path)
    response.raise_for_status()
    data = response.text
    return serializers[ser](data)


def load_env(variable: str, ser: Serialization = Serialization.raw) -> Any:
    data = os.getenv(variable)
    try:
        return serializers[ser](data)
    except AttributeError as e:
        raise AttributeError(
            f"Unable to read environment variable {variable}: {repr(e)}"
        )


def load_module(name: str, _: Serialization = Serialization.raw) -> Any:
    if ":" in name:
        mod, fn = name.rsplit(":", maxsplit=1)
    else:
        mod, fn = name, ""
    imported = importlib.import_module(mod)
    if fn != "":
        return getattr(imported, fn)
    return imported


def load_s3(path: str, ser: Serialization = Serialization.raw) -> Any:
    if isinstance(boto3, type(None)):
        raise ImportError(
            "boto3 must be installed to load S3 paths. Use ``pip install sovereign[boto]``"
        )
    bucket, key = path.split("/", maxsplit=1)
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket, Key=key)
    data = "".join([chunk.decode() for chunk in response["Body"]])
    return serializers[ser](data)


def load_python(path: str, _: Serialization = Serialization.raw) -> ModuleType:
    p = str(Path(path).absolute())
    loader = SourceFileLoader(p, path=p)
    return loader.load_module(p)


def load_inline(path: str, _: Serialization = Serialization.raw) -> Any:
    return str(path)


loaders: Dict[str, Callable[[str, Serialization], Union[str, Any]]] = {
    "file": load_file,
    "pkgdata": load_package_data,
    "http": load_http,
    "https": load_http,
    "env": load_env,
    "module": load_module,
    "s3": load_s3,
    "python": load_python,
    "inline": load_inline,
}
