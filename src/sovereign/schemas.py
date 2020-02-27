import zlib
import multiprocessing
from datetime import datetime, timedelta
from pydantic import BaseModel, StrictBool, Field
from typing import List, Any
from jinja2 import Template
from sovereign.config_loader import load


class Source(BaseModel):
    type: str
    config: dict


class SourceMetadata(BaseModel):
    updated: datetime = datetime.fromtimestamp(0)
    count: int = 0

    def update_date(self):
        self.updated = datetime.now()

    def update_count(self, iterable):
        self.count = len(iterable)

    @property
    def is_stale(self):
        return self.updated < (datetime.now() - timedelta(minutes=2))

    def __str__(self):
        return f'Sources were last updated at {datetime.isoformat(self.updated)}. ' \
               f'There are {self.count} instances.'


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
    loaded_code: str = None
    loaded_content: Template = None
    loaded_source: str = None

    class Config:
        arbitrary_types_allowed = True

    @property
    def is_python_source(self):
        return self.path.startswith('python://')

    @property
    def code(self):
        if self.loaded_code is None:
            self.loaded_code = load(self.path)
        return self.loaded_code

    @property
    def content(self) -> Template:
        if self.loaded_content is None:
            self.loaded_content = load(self.path)
        return self.loaded_content

    @property
    def checksum(self) -> int:
        return zlib.adler32(self.source.encode())

    @property
    def source(self) -> str:
        if self.loaded_source is None:
            if 'jinja' in self.path:
                # The Jinja2 template serializer does not properly set a name
                # for the loaded template.
                # The repr for the template prints out as the memory address
                # This makes it really hard to generate a consistent version_info string
                # in rendered configuration.
                # For this reason, we re-load the template as a string instead, and create a checksum.
                path = self.path.replace('+jinja', '+string')
                self.loaded_source = load(path)
            elif self.is_python_source:
                # If the template specified is a python source file,
                # we can simply read and return the source of it.
                path = self.path.replace('python', 'file+string')
                self.loaded_source = load(path)
            else:
                # The only other supported serializers are string, yaml, and json
                # So it should be safe to create this checksum off
                return str(self.content)
        return self.loaded_source


class Locality(BaseModel):
    region: str = Field(None)
    zone: str = Field(None)
    sub_zone: str = Field(None)


class SemanticVersion(BaseModel):
    major: int = 0
    minor: int = 0
    patch: int = 0

    def __str__(self):
        return f'{self.major}.{self.minor}.{self.patch}'


class BuildVersion(BaseModel):
    version: SemanticVersion = SemanticVersion()
    metadata: dict = {}


class Extension(BaseModel):
    name: str = None
    category: str = None
    version: BuildVersion = None
    disabled: bool = None


class Node(BaseModel):
    id: str = Field('-', title='Hostname')
    cluster: str = Field(
        ...,
        title='Envoy service-cluster',
        description='The ``--service-cluster`` configured by the Envoy client'
    )
    metadata: dict = Field(None, title='Key:value metadata')
    locality: Locality = Field(Locality(), title='Locality')
    build_version: str = Field(
        None,  # Optional in the v3 Envoy API
        title='Envoy build/release version string',
        description='Used to identify what version of Envoy the '
                    'client is running, and what config to provide in response'
    )
    user_agent_name: str = 'envoy'
    user_agent_version: str = ''
    user_agent_build_version: BuildVersion = BuildVersion()
    extensions: List[Extension] = []
    client_features: List[str] = []

    @property
    def common(self):
        """
        Returns fields that are the same in adjacent proxies
        ie. proxies that are part of the same logical group
        """
        return (
            self.cluster,
            self.build_version,
            self.user_agent_version,
            self.user_agent_build_version,
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
    node: Node = Field(..., title='Node information about the envoy proxy')
    version_info: str = Field('0', title='The version of the envoy clients current configuration')
    resource_names: Resources = Field(Resources(), title='List of requested resource names')

    @property
    def envoy_version(self):
        try:
            version = str(self.node.user_agent_build_version.version)
            assert version != '0.0.0'
        except AssertionError:
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
    version_info: str = Field(..., title='The version of the configuration in the response')
    resources: List[Any] = Field(..., title='The requested configuration resources')


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
