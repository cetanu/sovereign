import os
import json
from enum import Enum
from typing import Any, Dict, Callable, Union
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
    yaml = "yaml"
    json = "json"
    orjson = "orjson"
    ujson = "ujson"
    jinja = "jinja"
    jinja2 = "jinja2"
    string = "string"
    raw = "raw"


class Protocol(Enum):
    file = "file"
    http = "http"
    https = "https"
    pkgdata = "pkgdata"
    env = "env"
    module = "module"
    s3 = "s3"
    python = "python"
    inline = "inline"


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


class Loadable(BaseModel):
    protocol: Protocol = Protocol.http
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
    def from_legacy_fmt(s: str) -> "Loadable":
        if "://" not in s:
            return Loadable(
                protocol=Protocol.inline, serialization=Serialization.string, path=s
            )
        try:
            scheme, path = s.split("://")
        except ValueError:
            raise ValueError(s)
        try:
            p, s = scheme.split("+")
        except ValueError:
            p, s = scheme, "yaml"

        proto: Protocol = Protocol(p)
        serialization: Serialization = Serialization(s)
        if proto in (Protocol.python, Protocol.module):
            serialization = Serialization.raw
        if proto in (Protocol.http, Protocol.https):
            path = "://".join([proto.value, path])

        return Loadable(
            protocol=proto,
            serialization=serialization,
            path=path,
        )


def raise_(e: Exception) -> Exception:
    raise e


def load_file(path: str, loader: Serialization) -> Any:
    with open(path) as f:
        contents = f.read()
        try:
            return serializers[loader](contents)
        except FileNotFoundError:
            raise FileNotFoundError(f"Unable to load {path}")


def load_package_data(path: str, loader: Serialization) -> Any:
    pkg, pkg_file = path.split(":")
    data = get_package_file_bytes(pkg, pkg_file)
    return serializers[loader](data)


def load_http(path: str, loader: Serialization) -> Any:
    response = requests.get(path)
    response.raise_for_status()
    data = response.text
    return serializers[loader](data)


def load_env(variable: str, loader: Serialization = Serialization.raw) -> Any:
    data = os.getenv(variable)
    try:
        return serializers[loader](data)
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


def load_s3(path: str, loader: Serialization = Serialization.raw) -> Any:
    if isinstance(boto3, type(None)):
        raise ImportError(
            "boto3 must be installed to load S3 paths. Use ``pip install sovereign[boto]``"
        )
    bucket, key = path.split("/", maxsplit=1)
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket, Key=key)
    data = "".join([chunk.decode() for chunk in response["Body"]])
    return serializers[loader](data)


def load_python(path: str, _: Serialization = Serialization.raw) -> ModuleType:
    p = str(Path(path).absolute())
    loader = SourceFileLoader(p, path=p)
    return loader.load_module(p)


def load_inline(path: str, _: Serialization = Serialization.raw) -> Any:
    return str(path)


loaders: Dict[Protocol, Callable[[str, Serialization], Union[str, Any]]] = {
    Protocol.file: load_file,
    Protocol.pkgdata: load_package_data,
    Protocol.http: load_http,
    Protocol.https: load_http,
    Protocol.env: load_env,
    Protocol.module: load_module,
    Protocol.s3: load_s3,
    Protocol.python: load_python,
    Protocol.inline: load_inline,
}
