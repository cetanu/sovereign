import os
import zlib
from dataclasses import dataclass, field
from typing import List
from jinja2 import Template
from sovereign.config_loader import load


@dataclass
class Source:
    type: str
    config: dict


@dataclass
class StatsdConfig:
    host: str = '127.0.0.1'
    port: int = 8125
    tags: dict = field(default_factory=dict)
    namespace: str = 'sovereign'
    enabled: bool = False


@dataclass
class XdsTemplate:
    path: str
    content: Template = field(init=False)
    checksum: int = field(init=False)

    def __post_init__(self):
        self.content = load(self.path)
        self.checksum = zlib.adler32(self.source.encode())

    @property
    def source(self):
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


@dataclass(frozen=True)
class SovereignConfig:
    templates:                dict
    template_context:         dict
    sources:                  List[Source]
    eds_priority_matrix:      dict = field(default_factory=dict)
    modifiers:                List[str] = field(default_factory=list)
    global_modifiers:         List[str] = field(default_factory=list)
    regions:                  List[str] = field(default_factory=list)
    statsd:                   dict = field(default_factory=dict)
    auth_enabled:             bool = bool(os.getenv('SOVEREIGN_AUTH_ENABLED', False))
    auth_passwords:           str = os.getenv('SOVEREIGN_AUTH_PASSWORDS', '')
    encryption_key:           str = os.getenv('SOVEREIGN_ENCRYPTION_KEY', os.getenv('FERNET_ENCRYPTION_KEY'))
    no_changes_response_code: int = int(os.getenv('SOVEREIGN_NO_CHANGE_RESPONSE', 304))
    application_host:         str = os.getenv('SOVEREIGN_HOST', '0.0.0.0')
    application_port:         int = int(os.getenv('SOVEREIGN_PORT', '8080'))
    environment:              str = os.getenv('SOVEREIGN_ENVIRONMENT_TYPE', os.getenv('MICROS_ENVTYPE', 'local'))
    debug_enabled:            bool = bool(os.getenv('SOVEREIGN_DEBUG', False))
    sentry_dsn:               str = os.getenv('SOVEREIGN_SENTRY_DSN')

    @property
    def metrics(self):
        return StatsdConfig(**dict(self.statsd))

    @property
    def passwords(self):
        return self.auth_passwords.split(',') or []
