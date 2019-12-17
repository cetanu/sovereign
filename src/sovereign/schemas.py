import zlib
import multiprocessing
from pydantic import BaseModel, Schema, StrictBool
from typing import List, Any
from jinja2 import Template
from sovereign.config_loader import load


class Source(BaseModel):
    type: str
    config: dict


class StatsdConfig(BaseModel):
    host: str = '127.0.0.1'
    port: int = 8125
    tags: dict = dict()
    namespace: str = 'sovereign'
    enabled: bool = False
    use_ms: bool = True

    @property
    def loaded_tags(self):
        return {k: load(v) for k, v in self.tags.items()}


class XdsTemplate(BaseModel):
    path: str

    @property
    def is_python_source(self):
        return self.path.startswith('python://')

    @property
    def code(self):
        return load(self.path)

    @property
    def content(self) -> Template:
        return load(self.path)

    @property
    def checksum(self) -> int:
        return zlib.adler32(self.source.encode())

    @property
    def source(self) -> str:
        if 'jinja' in self.path:
            # The Jinja2 template serializer does not properly set a name
            # for the loaded template.
            # The repr for the template prints out as the memory address
            # This makes it really hard to generate a consistent version_info string
            # in rendered configuration.
            # For this reason, we re-load the template as a string instead, and create a checksum.
            path = self.path.replace('+jinja', '+string')
            return load(path)
        elif self.is_python_source:
            # If the template specified is a python source file,
            # we can simply read and return the source of it.
            path = self.path.replace('python', 'file+string')
            return load(path)
        else:
            # The only other supported serializers are string, yaml, and json
            # So it should be safe to create this checksum off
            return str(self.content)


class Locality(BaseModel):
    region: str = Schema(None)
    zone: str = Schema(None)
    sub_zone: str = Schema(None)


class Node(BaseModel):
    id: str = Schema('-', title='Hostname')
    cluster: str = Schema(
        ...,
        title='Envoy service-cluster',
        description='The ``--service-cluster`` configured by the Envoy client'
    )
    build_version: str = Schema(
        ...,
        title='Envoy build/release version string',
        description='Used to identify what version of Envoy the '
                    'client is running, and what config to provide in response'
    )
    metadata: dict = Schema(None, title='Key:value metadata')
    locality: Locality = Schema(Locality(), title='Locality')

    @property
    def common(self):
        """
        Returns fields that are the same in adjacent proxies
        ie. proxies that are part of the same logical group
        """
        return (
            self.cluster,
            self.build_version,
            self.locality,
        )


class Resources(list):
    """
    Acts like a regular list except it returns True
    for all membership tests when empty.
    """

    def __contains__(self, item):
        if len(self) == 0:
            return True
        return item in list(self)


class DiscoveryRequest(BaseModel):
    node: Node
    version_info: str = Schema('0', title='The version of the envoy clients current configuration')
    resource_names: Resources = Schema(Resources(), title='List of requested resource names')

    @property
    def envoy_version(self):
        try:
            build_version = self.node.build_version
            revision, version, *other_metadata = build_version.split('/')
        except (AttributeError, ValueError):
            # TODO: log/metric this?
            return 'default'
        return version

    @property
    def resources(self):
        return Resources(self.resource_names)


class DiscoveryResponse(BaseModel):
    version_info: str = Schema(..., title='The version of the configuration in the response')
    resources: List[Any] = Schema(..., title='The requested configuration resources')


class SovereignAsgiConfig(BaseModel):
    host: str         = load('env://SOVEREIGN_HOST', '0.0.0.0')
    port: int         = load('env://SOVEREIGN_PORT', 8080)
    keepalive: int    = load('env://SOVEREIGN_KEEPALIVE', 5)
    workers: int      = load('env://SOVEREIGN_WORKERS', (multiprocessing.cpu_count() * 2) + 1)
    reuse_port: bool  = True
    log_level: str    = 'warning'
    worker_class: str = 'uvicorn.workers.UvicornWorker'

    def as_gunicorn_conf(self):
        return {
            'bind': ':'.join(map(str, [self.host, self.port])),
            'keepalive': self.keepalive,
            'reuse_port': self.reuse_port,
            'loglevel': self.log_level,
            'workers': self.workers,
            'worker_class': self.worker_class
        }


class SovereignConfig(BaseModel):
    sources: List[Source]
    templates: dict
    template_context: dict         = {}
    eds_priority_matrix: dict      = {}
    modifiers: List[str]           = []
    global_modifiers: List[str]    = []
    regions: List[str]             = []
    statsd: StatsdConfig           = StatsdConfig()
    auth_enabled: StrictBool       = load('env://SOVEREIGN_AUTH_ENABLED', False)
    auth_passwords: str            = load('env://SOVEREIGN_AUTH_PASSWORDS', '')
    encryption_key: str            = load('env://SOVEREIGN_ENCRYPTION_KEY', '') or load('env://FERNET_ENCRYPTION_KEY', '')
    environment: str               = load('env://SOVEREIGN_ENVIRONMENT_TYPE', '') or load('env://MICROS_ENVTYPE', 'local')
    debug_enabled: StrictBool      = load('env://SOVEREIGN_DEBUG', False)
    sentry_dsn: str                = load('env://SOVEREIGN_SENTRY_DSN', '')
    node_match_key: str            = load('env://SOVEREIGN_NODE_MATCH_KEY', 'cluster')
    node_matching: StrictBool      = load('env://SOVEREIGN_MATCHING_ENABLED', True)
    source_match_key: str          = load('env://SOVEREIGN_SOURCE_MATCH_KEY', 'service_clusters')
    sources_refresh_rate: int      = load('env://SOVEREIGN_SOURCES_REFRESH_RATE', 30)
    refresh_context: StrictBool    = load('env://SOVEREIGN_REFRESH_CONTEXT', False)
    context_refresh_rate: int      = load('env://SOVEREIGN_CONTEXT_REFRESH_RATE', 3600)
    dns_hard_fail: StrictBool      = load('env://SOVEREIGN_DNS_HARD_FAIL', False)
    enable_access_logs: StrictBool = load('env://SOVEREIGN_ENABLE_ACCESS_LOGS', True)

    @property
    def passwords(self):
        return self.auth_passwords.split(',') or []

    @property
    def xds_templates(self):
        ret = {
            '__any__': {}  # Special key to hold templates from all versions
        }
        for version, templates in self.templates.items():
            loaded_templates = {
                _type: XdsTemplate(path=path)
                for _type, path in templates.items()
            }
            ret[version] = loaded_templates
            ret['__any__'].update(loaded_templates)
        return ret

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        kwargs = [
            f'{k}={v}'
            for k, v in self.show().items()
        ]
        return f'SovereignConfig({kwargs})'

    def show(self):
        safe_items = dict()
        for key, value in self.__dict__.items():
            if key in ['auth_passwords', 'encryption_key', 'passwords', 'sentry_dsn']:
                value = 'redacted'
            safe_items[key] = value
        return safe_items
