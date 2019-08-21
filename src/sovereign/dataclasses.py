import zlib
from dataclasses import dataclass, field
from typing import List, Dict
from datadog import statsd
from sovereign.config_loader import load, is_parseable


@dataclass
class ConfigLoaderPath:
    path: str

    def __post_init__(self):
        if not is_parseable(self.path):
            raise ValueError('Path cannot be loaded by any config_loader')


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
    content: str
    checksum: int = field(init=False)

    def __post_init__(self):
        self.checksum = zlib.adler32(self.content.encode())


@dataclass
class SovereignConfig:
    templates:                dict = field(default_factory=dict)
    template_context:         Dict[str, ConfigLoaderPath] = field(default_factory=dict)
    eds_priority_matrix:      dict = field(default_factory=dict)
    sources:                  List[Source] = field(default_factory=list)
    modifiers:                List[str] = field(default_factory=list)
    global_modifiers:         List[str] = field(default_factory=list)
    regions:                  List[str] = field(default_factory=list)
    statsd:                   StatsdConfig = field(default_factory=StatsdConfig)
    auth_enabled:             bool = False
    no_changes_response_code: int = 304

    def __post_init__(self):
        if isinstance(self.statsd, dict):
            self.statsd = StatsdConfig(**self.statsd)
