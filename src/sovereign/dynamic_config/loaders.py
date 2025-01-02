import os
import importlib
from typing import Any, Protocol
from pathlib import Path
from importlib.machinery import SourceFileLoader

import requests

from sovereign.utils.resources import get_package_file_bytes

try:
    import boto3

    BOTO_IS_AVAILABLE = True
except ImportError:
    BOTO_IS_AVAILABLE = False


class CustomLoader(Protocol):
    """
    Custom loaders can be added to sovereign by creating a subclass
    and then in config:

    template_context:
      context:
          ...:
            protocol: <loader name>
            serialization: ...
            path: <path argument>
    """

    default_deser: str = "yaml"

    def load(self, path: str) -> Any: ...


class File(CustomLoader):
    default_deser = "passthrough"

    def load(self, path: str) -> Any:
        with open(path) as f:
            contents = f.read()
            try:
                return contents
            except FileNotFoundError:
                raise FileNotFoundError(f"Unable to load {path}")


class PackageData(CustomLoader):
    default_deser = "string"

    def load(self, path: str) -> Any:
        pkg, pkg_file = path.split(":")
        data = get_package_file_bytes(pkg, pkg_file)
        return data


class Web(CustomLoader):
    default_deser = "json"

    def load(self, path: str) -> Any:
        response = requests.get(path)
        response.raise_for_status()
        data = response.text
        return data


class EnvironmentVariable(CustomLoader):
    default_deser = "raw"

    def load(self, path: str) -> Any:
        data = os.getenv(path)
        if data is None:
            raise AttributeError(f"Unable to read environment variable {path}")
        return data


class PythonModule(CustomLoader):
    default_deser = "passthrough"

    def load(self, path: str) -> Any:
        if ":" in path:
            mod, fn = path.rsplit(":", maxsplit=1)
        else:
            mod, fn = path, ""
        imported = importlib.import_module(mod)
        if fn != "":
            return getattr(imported, fn)
        return imported


class S3Bucket(CustomLoader):
    default_deser = "raw"

    def load(self, path: str) -> Any:
        if not BOTO_IS_AVAILABLE:
            raise ImportError(
                "boto3 must be installed to load S3 paths. Use ``pip install sovereign[boto]``"
            )
        bucket, key = path.split("/", maxsplit=1)
        s3 = boto3.client("s3")
        response = s3.get_object(Bucket=bucket, Key=key)
        data = "".join([chunk.decode() for chunk in response["Body"]])
        return data


class PythonInlineCode(CustomLoader):
    default_deser = "passthrough"

    def load(self, path: str) -> Any:
        p = str(Path(path).absolute())
        loader = SourceFileLoader(p, path=p)
        return loader.load_module(p)


class Inline(CustomLoader):
    default_deser = "string"

    def load(self, path: str) -> Any:
        return path
