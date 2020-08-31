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
import yaml
import jinja2
import requests
import importlib
from importlib.machinery import SourceFileLoader
from pathlib import Path
from pkg_resources import resource_string


jinja_env = jinja2.Environment(enable_async=True, autoescape=True)

serializers = {
    'yaml': yaml.safe_load,
    'json': json.loads,
    'jinja': jinja_env.from_string,
    'jinja2': jinja_env.from_string,
    'string': str,
}


def raise_(e):
    raise e


try:
    import ujson
    serializers['ujson'] = ujson.loads
    jinja_env.policies['json.dumps_function'] = ujson.dumps  # Changes the json dumper in jinja2
except ImportError:
    # This lambda will raise an exception when the serializer is used; otherwise we should not crash
    serializers['ujson'] = lambda *a, **kw: raise_(ImportError('ujson must be installed to use in config_loaders'))

try:
    import orjson
    serializers['orjson'] = orjson.loads
    # orjson.dumps returns bytes, so we have to wrap & decode it
    jinja_env.policies['json.dumps_function'] = lambda *a, **kw: orjson.dumps(*a, **kw).decode()
    jinja_env.policies['json.dumps_kwargs'] = {'option': orjson.OPT_SORT_KEYS}  # default in jinja is to sort keys
except ImportError:
    # This lambda will raise an exception when the serializer is used; otherwise we should not crash
    serializers['orjson'] = lambda *a, **kw: raise_(ImportError('orjson must be installed to use in config_loaders'))

try:
    import boto3
except ImportError:
    boto3 = None


def load_file(path, loader):
    with open(path) as f:
        contents = f.read()
        try:
            return serializers[loader](contents)
        except FileNotFoundError:
            raise FileNotFoundError(f'Unable to load {path}')


def load_package_data(path, loader):
    pkg, pkg_file = path.split(':')
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
        raise AttributeError(f'Unable to read environment variable {variable}: {repr(e)}')


def load_module(name, _=None):
    return importlib.import_module(name)


def load_s3(path: str, loader=None):
    if isinstance(boto3, type(None)):
        raise ImportError('boto3 must be installed to load S3 paths. Use ``pip install sovereign[boto]``')
    bucket, key = path.split('/', maxsplit=1)
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=bucket, Key=key)
    data = ''.join([chunk.decode() for chunk in response['Body']])
    return serializers[loader](data)


def load_python(path, _=None):
    p = Path(path).absolute()
    loader = SourceFileLoader(p.name, path=str(p))
    return loader.load_module(p.name)


loaders = {
    'file': load_file,
    'pkgdata': load_package_data,
    'http': load_http,
    'https': load_http,
    'env': load_env,
    'module': load_module,
    's3': load_s3,
    'python': load_python,
}


def parse_spec(spec, default_serialization='yaml'):
    serialization = default_serialization
    scheme, path = spec.split('://')
    if '+' in scheme:
        scheme, serialization = scheme.split('+')
    if 'http' in scheme:
        path = '://'.join([scheme, path])
    return scheme, path, serialization


def is_parseable(spec):
    if '://' not in spec:
        return False
    scheme, _, serialization = parse_spec(spec)
    return (
        scheme in loaders and
        serialization in serializers
    )


def load(spec, default=None):
    if '://' not in spec:
        return spec
    scheme, path, serialization = parse_spec(spec)

    try:
        return loaders[scheme](path, serialization)
    except Exception:
        if default is not None:
            return default
        raise
