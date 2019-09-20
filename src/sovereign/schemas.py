import os
import zlib
from pydantic import BaseModel, Schema
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

    @property
    def loaded_tags(self):
        return {k: load(v) for k, v in self.tags.items()}


class XdsTemplate(BaseModel):
    path: str

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
    locality: Locality = Schema(None, title='Locality')


class DiscoveryRequest(BaseModel):
    node: Node
    version_info: str = Schema('0', title='The version of the envoy clients current configuration')
    resource_names: List[str] = Schema(list(), title='List of requested resource names')

    @property
    def envoy_version(self):
        try:
            build_version = self.node.build_version
            revision, version, *other_metadata = build_version.split('/')
        except (AttributeError, ValueError):
            # TODO: log/metric this?
            return 'default'
        return version


class DiscoveryResponse(BaseModel):
    version_info: str = Schema(..., title='The version of the configuration in the response')
    resources: List[Any] = Schema(..., title='The requested configuration resources')


class SovereignConfig(BaseModel):
    sources: List[Source]
    templates: dict
    template_context: dict = {}
    eds_priority_matrix: dict = {}
    modifiers: List[str] = []
    global_modifiers: List[str] = []
    regions: List[str] = []
    statsd: StatsdConfig = None
    auth_enabled: bool = os.getenv('SOVEREIGN_AUTH_ENABLED', False)
    auth_passwords: str = os.getenv('SOVEREIGN_AUTH_PASSWORDS', '')
    encryption_key: str = os.getenv('SOVEREIGN_ENCRYPTION_KEY', os.getenv('FERNET_ENCRYPTION_KEY'))
    no_changes_response_code: int = os.getenv('SOVEREIGN_NO_CHANGE_RESPONSE', 304)
    environment: str = os.getenv('SOVEREIGN_ENVIRONMENT_TYPE', os.getenv('MICROS_ENVTYPE', 'local'))
    debug_enabled: bool = os.getenv('SOVEREIGN_DEBUG', False)
    sentry_dsn: str = os.getenv('SOVEREIGN_SENTRY_DSN')
    node_match_key: str = os.getenv('SOVEREIGN_NODE_MATCH_KEY', 'cluster')
    node_matching: bool = os.getenv('SOVEREIGN_MATCHING_ENABLED', True)
    source_match_key: str = os.getenv('SOVEREIGN_SOURCE_MATCH_KEY', 'service_clusters')
    sources_refresh_rate: int = os.getenv('SOVEREIGN_SOURCES_REFRESH_RATE', 30)
    refresh_context: bool = os.getenv('SOVEREIGN_REFRESH_CONTEXT', False)
    context_refresh_rate: int = os.getenv('SOVEREIGN_CONTEXT_REFRESH_RATE', 3600)

    @property
    def passwords(self):
        return self.auth_passwords.split(',') or []
