"""
Configuration Loader
--------------------
Various functions that assist in loading initial configuration for the
control plane.

The control plane accepts a main configuration file from the environment
variable ``SOVEREIGN_CONFIG`` which follows the format:

.. code-block:: none

   <scheme>://path[,<scheme>://path,...]

Examples:

.. code-block:: none

   # Single file
     file:///etc/sovereign.yaml

   # Multiple files (comma separated)
     file:///etc/sovereign/common.yaml,file:///etc/sovereign/dev.yaml

   # Other types of sources
     http://config.myserver.com/environments/dev.yaml

   # Other types of formats
     http+json://config.myserver.com/environments/dev.json
     http+jinja://config.myserver.com/environments/dev.j2
     http+yaml://config.myserver.com/environments/dev.yaml

"""
import os
import json
from enum import Enum
from typing import Optional
import yaml
import jinja2
import requests
import importlib
from importlib.machinery import SourceFileLoader
from pathlib import Path
from pkg_resources import resource_string
from pydantic import BaseModel


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


jinja_env = jinja2.Environment(enable_async=True, autoescape=True)


def passthrough(item):
    return item


def string(item):
    return str(item)


serializers = {
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
    jinja_env.policies[
        "json.dumps_function"
    ] = ujson.dumps  # Changes the json dumper in jinja2
except ImportError:
    # This lambda will raise an exception when the serializer is used; otherwise we should not crash
    serializers[Serialization.ujson] = lambda *a, **kw: raise_(
        ImportError("ujson must be installed to use in config_loaders")
    )

try:
    import orjson

    serializers[Serialization.orjson] = orjson.loads

    # orjson.dumps returns bytes, so we have to wrap & decode it
    def orjson_dumps(*args, **kwargs):
        try:
            representation = orjson.dumps(*args, **kwargs)
        except TypeError:
            raise TypeError(f"Unable to dump objects using ORJSON: {args}, {kwargs}")
        try:
            return representation.decode()
        except Exception as e:
            raise e.__class__(
                f"Unable to decode ORJSON: {representation}. Original exception: {e}"
            )

    jinja_env.policies["json.dumps_function"] = orjson_dumps
    jinja_env.policies["json.dumps_kwargs"] = {
        "option": orjson.OPT_SORT_KEYS
    }  # default in jinja is to sort keys
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
    serialization: Optional[Serialization] = Serialization.yaml
    path: str

    def load(self, default=None):
        try:
            return loaders[self.protocol](self.path, self.serialization)
        except Exception:
            if default is not None:
                return default
            raise

    @staticmethod
    def from_legacy_fmt(s: str):
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


def raise_(e):
    raise e


def load_file(path, loader):
    with open(path) as f:
        contents = f.read()
        try:
            return serializers[loader](contents)
        except FileNotFoundError:
            raise FileNotFoundError(f"Unable to load {path}")


def load_package_data(path, loader):
    pkg, pkg_file = path.split(":")
    data = resource_string(pkg, pkg_file)
    try:
        data = data.decode()
    except AttributeError:
        pass
    return serializers[loader](data)


def load_http(path, loader):
    response = requests.get(path)
    response.raise_for_status()
    data = response.text
    return serializers[loader](data)


def load_env(variable, loader=None):
    data = os.getenv(variable)
    try:
        return serializers[loader](data)
    except AttributeError as e:
        raise AttributeError(
            f"Unable to read environment variable {variable}: {repr(e)}"
        )


def load_module(name, _=None):
    return importlib.import_module(name)


def load_s3(path: str, loader=None):
    if isinstance(boto3, type(None)):
        raise ImportError(
            "boto3 must be installed to load S3 paths. Use ``pip install sovereign[boto]``"
        )
    bucket, key = path.split("/", maxsplit=1)
    s3 = boto3.client("s3")
    response = s3.get_object(Bucket=bucket, Key=key)
    data = "".join([chunk.decode() for chunk in response["Body"]])
    return serializers[loader](data)


def load_python(path, _=None):
    p = Path(path).absolute()
    loader = SourceFileLoader(p.name, path=str(p))
    return loader.load_module(p.name)


def load_inline(path, _=None):
    return str(path)


loaders = {
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
