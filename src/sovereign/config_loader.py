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
import importlib
import yaml
import jinja2
import requests
from pkg_resources import resource_string


serializers = {
    'yaml': yaml.safe_load,
    'json': json.loads,
    'jinja': jinja2.Template
}


def load_file(path, loader):
    with open(path) as f:
        contents = f.read()
        return serializers[loader](contents)


def load_package_data(path, loader):
    pkg, pkg_file = path.split(':')
    data = resource_string(pkg, pkg_file)
    try:
        data = data.decode()
    except AttributeError:
        pass
    return serializers[loader](data)


def load_http(path, loader):
    data = requests.get(path).text
    return serializers[loader](data)


def load_env(variable, loader=None):
    data = os.getenv(variable)
    if loader is not None and data is not None:
        return serializers[loader](data)
    return data


def load_module(name, _=None):
    return importlib.import_module(name)


loaders = {
    'file': load_file,
    'pkgdata': load_package_data,
    'http': load_http,
    'https': load_http,
    'env': load_env,
    'module': load_module
}


def load(spec):
    if '://' not in spec:
        return spec

    serialization = 'yaml'
    scheme, path = spec.split('://')
    if '+' in scheme:
        scheme, serialization = scheme.split('+')
    if 'http' in scheme:
        path = '://'.join([scheme, path])
    return loaders[scheme](path, serialization)
