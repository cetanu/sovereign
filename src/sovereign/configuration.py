import importlib
import multiprocessing
import os
import warnings
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from os import getenv
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    Optional,
    Self,
    Union,
)

from croniter import CroniterBadCronError, croniter
from pydantic import (
    BaseModel,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from sovereign.dynamic_config import Loadable
from sovereign.types import XdsTemplate
from sovereign.utils import dictupdate
from sovereign.utils.crypto.suites import EncryptionType


class CacheStrategy(str, Enum):
    context = "context"
    content = "content"


class SourceData(BaseModel):
    scopes: Dict[str, list[Dict[str, Any]]] = Field(default_factory=dict)


class ConfiguredSource(BaseModel):
    type: str
    config: Dict[str, Any]
    scope: str = "default"  # backward compatibility


class StatsdConfig(BaseModel):
    host: str = "127.0.0.1"
    port: Union[int, str] = 8125
    tags: Dict[str, Union[Loadable, str]] = dict()
    namespace: str = "sovereign"
    enabled: bool = False
    use_ms: bool = True

    @field_validator("host", mode="before")
    @classmethod
    def load_host(cls, v: str) -> Any:
        return Loadable.from_legacy_fmt(v).load()

    @field_validator("port", mode="before")
    @classmethod
    def load_port(cls, v: Union[int, str]) -> Any:
        if isinstance(v, int):
            return v
        elif isinstance(v, str):
            return Loadable.from_legacy_fmt(v).load()
        else:
            raise ValueError(f"Received an invalid port: {v}")

    @field_validator("tags", mode="before")
    @classmethod
    def load_tags(cls, v: Dict[str, Union[Loadable, str]]) -> Dict[str, Any]:
        ret = dict()
        for key, value in v.items():
            if isinstance(value, dict):
                ret[key] = Loadable(**value).load()
            elif isinstance(value, str):
                ret[key] = Loadable.from_legacy_fmt(value).load()
            else:
                raise ValueError(f"Received an invalid tag for statsd: {value}")
        return ret


class SovereignAsgiConfig(BaseSettings):
    user: Optional[str] = Field(None, alias="SOVEREIGN_USER")
    host: str = Field("0.0.0.0", alias="SOVEREIGN_HOST")
    port: int = Field(8080, alias="SOVEREIGN_PORT")
    keepalive: int = Field(5, alias="SOVEREIGN_KEEPALIVE")
    workers: int = Field(
        default_factory=lambda: multiprocessing.cpu_count() * 2 + 1,
        alias="SOVEREIGN_WORKERS",
    )
    threads: int = Field(1, alias="SOVEREIGN_THREADS")
    reuse_port: bool = True
    preload_app: bool = Field(True, alias="SOVEREIGN_PRELOAD")
    log_level: str = "warning"
    worker_class: str = "uvicorn.workers.UvicornWorker"
    worker_timeout: int = Field(30, alias="SOVEREIGN_WORKER_TIMEOUT")
    worker_tmp_dir: Optional[str] = Field(None, alias="SOVEREIGN_WORKER_TMP_DIR")
    graceful_timeout: Optional[int] = Field(None)
    max_requests: int = Field(0, alias="SOVEREIGN_MAX_REQUESTS")
    max_requests_jitter: int = Field(0, alias="SOVEREIGN_MAX_REQUESTS_JITTER")
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    @model_validator(mode="after")
    def validate_graceful_timeout(self) -> Self:
        if self.graceful_timeout is None:
            self.graceful_timeout = self.worker_timeout * 2
        return self

    def as_gunicorn_conf(self) -> Dict[str, Any]:
        ret = {
            "bind": ":".join(map(str, [self.host, self.port])),
            "keepalive": self.keepalive,
            "reuse_port": self.reuse_port,
            "preload_app": self.preload_app,
            "loglevel": self.log_level,
            "timeout": self.worker_timeout,
            "threads": self.threads,
            "workers": self.workers,
            "worker_class": self.worker_class,
            "graceful_timeout": self.graceful_timeout,
            "max_requests": self.max_requests,
            "max_requests_jitter": self.max_requests_jitter,
        }
        if self.worker_tmp_dir is not None:
            ret["worker_tmp_dir"] = self.worker_tmp_dir
        return ret


class TemplateSpecification(BaseModel):
    type: str
    spec: Loadable
    depends_on: list[str] = Field(default_factory=list)


class NodeMatching(BaseSettings):
    enabled: bool = Field(True, alias="SOVEREIGN_NODE_MATCHING_ENABLED")
    source_key: str = Field("service_clusters", alias="SOVEREIGN_SOURCE_MATCH_KEY")
    node_key: str = Field("cluster", alias="SOVEREIGN_NODE_MATCH_KEY")
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )


@dataclass
class EncryptionConfig:
    encryption_key: str
    encryption_type: EncryptionType


class AuthConfiguration(BaseSettings):
    enabled: bool = Field(False, alias="SOVEREIGN_AUTH_ENABLED")
    auth_passwords: SecretStr = Field(SecretStr(""), alias="SOVEREIGN_AUTH_PASSWORDS")
    encryption_key: SecretStr = Field(SecretStr(""), alias="SOVEREIGN_ENCRYPTION_KEY")
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    @staticmethod
    def _create_encryption_config(encryption_key_setting: str) -> EncryptionConfig:
        encryption_key, _, encryption_type_raw = encryption_key_setting.partition(":")
        if encryption_type_raw:
            encryption_type = EncryptionType(encryption_type_raw)
        else:
            encryption_type = EncryptionType.FERNET
        return EncryptionConfig(encryption_key, encryption_type)

    @property
    def encryption_configs(self) -> tuple[EncryptionConfig, ...]:
        secret_values = self.encryption_key.get_secret_value().split()

        configs = tuple(
            self._create_encryption_config(encryption_key_setting)
            for encryption_key_setting in secret_values
        )
        return configs


class ApplicationLogConfiguration(BaseSettings):
    enabled: bool = Field(False, alias="SOVEREIGN_ENABLE_APPLICATION_LOGS")
    log_fmt: Optional[str] = Field(None, alias="SOVEREIGN_APPLICATION_LOG_FORMAT")
    # currently only support /dev/stdout as JSON
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )


class AccessLogConfiguration(BaseSettings):
    enabled: bool = Field(True, alias="SOVEREIGN_ENABLE_ACCESS_LOGS")
    log_fmt: Optional[str] = Field(None, alias="SOVEREIGN_LOG_FORMAT")
    ignore_empty_fields: bool = Field(False, alias="SOVEREIGN_LOG_IGNORE_EMPTY")
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )


class LoggingConfiguration(BaseSettings):
    application_logs: ApplicationLogConfiguration = ApplicationLogConfiguration()
    access_logs: AccessLogConfiguration = AccessLogConfiguration()
    log_source_diffs: bool = False


class ContextFileCache(BaseSettings):
    file_path: str = ".sovereign_context_cache"
    algo: Optional[str] = None

    @property
    def path(self) -> Path:
        return Path(self.file_path)

    @property
    def hasher(self) -> Callable[[Any], Any]:
        lib = importlib.import_module("hashlib")
        return getattr(lib, self.algo or "sha256")


class ContextConfiguration(BaseSettings):
    context: Dict[str, Loadable] = {}
    cache: ContextFileCache = ContextFileCache()
    refresh: bool = Field(False, alias="SOVEREIGN_REFRESH_CONTEXT")
    refresh_rate: Optional[int] = Field(None, alias="SOVEREIGN_CONTEXT_REFRESH_RATE")
    refresh_cron: Optional[str] = Field(None, alias="SOVEREIGN_CONTEXT_REFRESH_CRON")
    refresh_num_retries: int = Field(3, alias="SOVEREIGN_CONTEXT_REFRESH_NUM_RETRIES")
    refresh_retry_interval_secs: int = Field(
        10, alias="SOVEREIGN_CONTEXT_REFRESH_RETRY_INTERVAL_SECS"
    )
    cooldown: int = Field(15, alias="SOVEREIGN_CONTEXT_REFRESH_COOLDOWN")
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    @staticmethod
    def context_from_legacy(context: Dict[str, str]) -> Dict[str, Loadable]:
        ret = dict()
        for key, value in context.items():
            ret[key] = Loadable.from_legacy_fmt(value)
        return ret

    @model_validator(mode="after")
    def validate_single_use_refresh_method(self) -> Self:
        if (self.refresh_rate is not None) and (self.refresh_cron is not None):
            raise RuntimeError(
                f"Only one of SOVEREIGN_CONTEXT_REFRESH_RATE or SOVEREIGN_CONTEXT_REFRESH_CRON can be defined. Got {self.refresh_rate=} and {self.refresh_cron=}"
            )
        return self

    @model_validator(mode="before")
    @classmethod
    def set_default_refresh_rate(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        refresh_rate = values.get("refresh_rate")
        refresh_cron = values.get("refresh_cron")

        if (refresh_rate is None) and (refresh_cron is None):
            values["refresh_rate"] = 3600
        return values

    @field_validator("refresh_cron")
    @classmethod
    def validate_refresh_cron(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not croniter.is_valid(v):
            raise CroniterBadCronError(f"'{v}' is not a valid cron expression")
        return v


class SourcesConfiguration(BaseSettings):
    refresh_rate: int = Field(30, alias="SOVEREIGN_SOURCES_REFRESH_RATE")
    max_retries: int = Field(3, alias="SOVEREIGN_SOURCES_MAX_RETRIES")
    retry_delay: int = Field(1, alias="SOVEREIGN_SOURCES_RETRY_DELAY")
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )


class TracingConfig(BaseSettings):
    enabled: bool = Field(False)
    collector: str = Field("notset")
    endpoint: str = Field("/v2/api/spans")
    trace_id_128bit: bool = Field(True)
    tags: Dict[str, Union[Loadable, str]] = dict()
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    @field_validator("tags", mode="before")
    @classmethod
    def load_tags(cls, v: Dict[str, Union[Loadable, str]]) -> Dict[str, Any]:
        ret = dict()
        for key, value in v.items():
            if isinstance(value, dict):
                ret[key] = Loadable(**value).load()
            elif isinstance(value, str):
                ret[key] = Loadable.from_legacy_fmt(value).load()
            else:
                raise ValueError(f"Received an invalid tag for tracing: {value}")
        return ret

    @model_validator(mode="before")
    @classmethod
    def set_environmental_variables(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if enabled := getenv("SOVEREIGN_TRACING_ENABLED"):
            values["enabled"] = enabled
        if collector := getenv("SOVEREIGN_TRACING_COLLECTOR"):
            values["collector"] = collector
        if endpoint := getenv("SOVEREIGN_TRACING_ENDPOINT"):
            values["endpoint"] = endpoint
        if trace_id_128bit := getenv("SOVEREIGN_TRACING_TRACE_ID_128BIT"):
            values["trace_id_128bit"] = trace_id_128bit
        return values


class SupervisordConfig(BaseSettings):
    nodaemon: bool = Field(True, alias="SOVEREIGN_SUPERVISORD_NODAEMON")
    loglevel: str = Field("error", alias="SOVEREIGN_SUPERVISORD_LOGLEVEL")
    pidfile: str = Field("/tmp/supervisord.pid", alias="SOVEREIGN_SUPERVISORD_PIDFILE")
    logfile: str = Field("/tmp/supervisord.log", alias="SOVEREIGN_SUPERVISORD_LOGFILE")
    directory: str = Field("%(here)s", alias="SOVEREIGN_SUPERVISORD_DIRECTORY")
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )


class LegacyConfig(BaseSettings):
    regions: Optional[list[str]] = None
    eds_priority_matrix: Optional[Dict[str, Dict[str, int]]] = None
    dns_hard_fail: Optional[bool] = Field(None, alias="SOVEREIGN_DNS_HARD_FAIL")
    environment: Optional[str] = Field(None, alias="SOVEREIGN_ENVIRONMENT")
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    @field_validator("regions")
    @classmethod
    def regions_is_set(cls, v: Optional[list[str]]) -> list[str]:
        if v is not None:
            warnings.warn(
                "Setting regions via config is deprecated. "
                "It is suggested to use a modifier or template "
                "logic in order to achieve the same goal.",
                DeprecationWarning,
            )
            return v
        else:
            return []

    @field_validator("eds_priority_matrix")
    @classmethod
    def eds_priority_matrix_is_set(
        cls, v: Optional[Dict[str, Dict[str, Any]]]
    ) -> Dict[str, Dict[str, Any]]:
        if v is not None:
            warnings.warn(
                "Setting eds_priority_matrix via config is deprecated. "
                "It is suggested to use a modifier or template "
                "logic in order to achieve the same goal.",
                DeprecationWarning,
            )
            return v
        else:
            return {}

    @field_validator("dns_hard_fail")
    @classmethod
    def dns_hard_fail_is_set(cls, v: Optional[bool]) -> bool:
        if v is not None:
            warnings.warn(
                "Setting dns_hard_fail via config is deprecated. "
                "It is suggested to supply a module that can perform "
                "dns resolution to template_context, so that it can "
                "be used via templates instead.",
                DeprecationWarning,
            )
            return v
        else:
            return False

    @field_validator("environment")
    @classmethod
    def environment_is_set(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            warnings.warn(
                "Setting environment via config is deprecated. "
                "It is suggested to configure this value through log_fmt "
                "instead.",
                DeprecationWarning,
            )
            return v
        else:
            return None


class TemplateConfiguration(BaseModel):
    default: list[TemplateSpecification]
    versions: dict[str, list[TemplateSpecification]] = Field(default_factory=dict)


def default_hash_rules():
    return [
        # Sovereign internal fields
        "template.version",
        "is_internal_request",
        "desired_controlplane",
        "resource_type",
        "api_version",
        "envoy_version",
        # Envoy fields from the real Discovery Request
        "resource_names",
        "node.cluster",
        "node.locality",
    ]


class CacheBackendConfig(BaseModel):
    type: str = Field(..., description="Cache backend type (e.g., 'redis', 's3')")
    config: dict[str, Any] = Field(
        default_factory=dict, description="Backend-specific configuration"
    )


class CacheConfiguration(BaseModel):
    hash_rules: list[str] = Field(
        default_factory=default_hash_rules,
        description="The set of JMES expressions against incoming Discovery Requests used to form a cache key.",
    )
    read_timeout: float = Field(
        5.0,
        description="How long to block when trying to read from the cache before giving up",
    )
    local_fs_path: str = Field(
        "/var/run/sovereign_cache",
        description="Local filesystem cache path. Used to provide fast responses to clients and reduce hits against remote cache backend.",
    )
    remote_backend: CacheBackendConfig | None = Field(
        None, description="Remote cache backend configuration"
    )


class SovereignConfigv2(BaseSettings):
    # Config generation
    templates: TemplateConfiguration
    template_context: ContextConfiguration = ContextConfiguration()

    # Web/Discovery
    authentication: AuthConfiguration = AuthConfiguration()

    # Cache
    cache: CacheConfiguration = CacheConfiguration()

    # Worker
    worker_host: Optional[str] = Field("localhost", alias="SOVEREIGN_WORKER_HOST")
    worker_port: Optional[int] = Field(9080, alias="SOVEREIGN_WORKER_PORT")

    # Supervisord settings
    supervisord: SupervisordConfig = SupervisordConfig()

    # Misc
    tracing: Optional[TracingConfig] = Field(default_factory=TracingConfig)
    debug: bool = Field(False, alias="SOVEREIGN_DEBUG")
    logging: LoggingConfiguration = LoggingConfiguration()
    statsd: StatsdConfig = StatsdConfig()
    sentry_dsn: SecretStr = Field(SecretStr(""), alias="SOVEREIGN_SENTRY_DSN")

    # Planned for removal/deprecated/blocked by circular context usage internally
    sources: Optional[list[ConfiguredSource]] = Field(None, deprecated=True)
    source_config: SourcesConfiguration = Field(
        default_factory=SourcesConfiguration, deprecated=True
    )
    matching: Optional[NodeMatching] = Field(
        default_factory=NodeMatching, deprecated=True
    )
    modifiers: list[str] = Field(default_factory=list, deprecated=True)
    global_modifiers: list[str] = Field(default_factory=list, deprecated=True)

    # Deprecated, need to migrate off internally
    legacy_fields: LegacyConfig = Field(default_factory=LegacyConfig, deprecated=True)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    @property
    def passwords(self) -> list[str]:
        return self.authentication.auth_passwords.get_secret_value().split(",") or []

    def xds_templates(self) -> dict[str, dict[str, XdsTemplate]]:
        ret: dict[str, dict[str, XdsTemplate]] = defaultdict(dict)
        for template in self.templates.default:
            ret["default"][template.type] = XdsTemplate(
                path=template.spec,
                resource_type=template.type,
                depends_on=template.depends_on,
            )
        for version, templates in self.templates.versions.items():
            for template in templates:
                loaded = XdsTemplate(
                    path=template.spec,
                    resource_type=template.type,
                    depends_on=template.depends_on,
                )
                ret[version][template.type] = loaded
                ret["__any__"][template.type] = loaded
        ret["__any__"].update(ret["default"])
        return ret

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"SovereignConfigv2({self.model_dump()})"

    def show(self) -> Dict[str, Any]:
        return self.model_dump()


def parse_raw_configuration(path: str) -> Mapping[Any, Any]:
    ret: Mapping[Any, Any] = dict()
    for p in path.split(","):
        spec = Loadable.from_legacy_fmt(p)
        ret = dictupdate.merge(obj_a=ret, obj_b=spec.load(), merge_lists=True)
    return ret


config_path = os.getenv("SOVEREIGN_CONFIG", "file:///etc/sovereign.yaml")
config = SovereignConfigv2(**parse_raw_configuration(config_path))

XDS_TEMPLATES = config.xds_templates()

# Create an enum that bases all the available discovery types off what has been configured
discovery_types = (_type for _type in sorted(XDS_TEMPLATES["__any__"].keys()))
discovery_types_base: Dict[str, str] = {t: t for t in discovery_types}
# TODO: this needs to be typed somehow, but I have no idea how
ConfiguredResourceTypes = Enum("DiscoveryTypes", discovery_types_base)  # type: ignore
