import multiprocessing
import warnings
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from os import getenv
from types import ModuleType
from typing import Any, Dict, List, Optional, Self, Tuple, Type, Union

from croniter import CroniterBadCronError, croniter
from fastapi.responses import JSONResponse
from jinja2 import Template, meta
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    model_validator,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from sovereign.config_loader import Loadable, Serialization, jinja_env
from sovereign.utils.crypto.suites import EncryptionType
from sovereign.utils.version_info import compute_hash

missing_arguments = {"missing", "positional", "arguments:"}

JsonResponseClass: Type[JSONResponse] = JSONResponse
# pylint: disable=unused-import
try:
    import orjson
    from fastapi.responses import ORJSONResponse

    JsonResponseClass = ORJSONResponse
except ImportError:
    try:
        import ujson
        from fastapi.responses import UJSONResponse

        JsonResponseClass = UJSONResponse
    except ImportError:
        pass


class CacheStrategy(str, Enum):
    context = "context"
    content = "content"


class SourceData(BaseModel):
    scopes: Dict[str, List[Dict[str, Any]]] = defaultdict(list)


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


class DiscoveryCacheConfig(BaseModel):
    enabled: bool = False
    host: str = "localhost"
    port: int = 6379
    secure: bool = False
    protocol: str = "redis://"
    password: SecretStr = SecretStr("")
    client_side: bool = True  # True = Try in-memory cache before hitting redis
    wait_for_connection_timeout: int = 5
    socket_connect_timeout: int = 5
    socket_timeout: int = 5
    max_connections: int = 100
    retry_on_timeout: bool = True  # Retry connections if they timeout.
    suppress: bool = False  # False = Don't suppress connection errors. True = suppress connection errors
    socket_keepalive: bool = True  # Try to keep connections to redis around.
    ttl: int = 60

    @model_validator(mode="after")
    def set_default_protocol(self) -> Self:
        if self.secure:
            self.protocol = "rediss://"
        return self

    @model_validator(mode="before")
    @classmethod
    def set_environmental_variables(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if host := getenv("SOVEREIGN_DISCOVERY_CACHE_REDIS_HOST"):
            values["host"] = host
        if port := getenv("SOVEREIGN_DISCOVERY_CACHE_REDIS_PORT"):
            values["port"] = int(port)
        if password := getenv("SOVEREIGN_DISCOVERY_CACHE_REDIS_PASSWORD"):
            values["password"] = SecretStr(password)
        return values


class XdsTemplate:
    def __init__(self, path: Union[str, Loadable]) -> None:
        if isinstance(path, str):
            self.loadable: Loadable = Loadable.from_legacy_fmt(path)
        elif isinstance(path, Loadable):
            self.loadable = path
        self.is_python_source = self.loadable.protocol == "python"
        self.source = self.load_source()
        template_ast = jinja_env.parse(self.source)
        self.jinja_variables = meta.find_undeclared_variables(template_ast)

    def __call__(
        self, *args: Any, **kwargs: Any
    ) -> Optional[Union[Dict[str, Any], str]]:
        if not hasattr(self, "code"):
            self.code: Union[Template, ModuleType] = self.loadable.load()
        if isinstance(self.code, ModuleType):
            try:
                return {"resources": list(self.code.call(*args, **kwargs))}
            except TypeError as e:
                if not set(str(e).split()).issuperset(missing_arguments):
                    raise e
                message_start = str(e).find(":")
                missing_args = str(e)[message_start + 2 :]
                supplied_args = list(kwargs.keys())
                raise TypeError(
                    f"Tried to render a template using partial arguments. "
                    f"Missing args: {missing_args}. Supplied args: {args} "
                    f"Supplied keyword args: {supplied_args}"
                )
        else:
            return self.code.render(*args, **kwargs)

    def load_source(self) -> str:
        if self.loadable.serialization in (Serialization.jinja, Serialization.jinja2):
            # The Jinja2 template serializer does not properly set a name
            # for the loaded template.
            # The repr for the template prints out as the memory address
            # This makes it really hard to generate a consistent version_info string
            # in rendered configuration.
            # For this reason, we re-load the template as a string instead, and create a checksum.
            old_serialization = self.loadable.serialization
            self.loadable.serialization = Serialization("string")
            ret = self.loadable.load()
            self.loadable.serialization = old_serialization
            return str(ret)
        elif self.is_python_source:
            # If the template specified is a python source file,
            # we can simply read and return the source of it.
            old_protocol = self.loadable.protocol
            old_serialization = self.loadable.serialization
            self.loadable.protocol = "inline"
            self.loadable.serialization = Serialization("string")
            ret = self.loadable.load()
            self.loadable.protocol = old_protocol
            self.loadable.serialization = old_serialization
            return str(ret)
        ret = self.loadable.load()
        return str(ret)

    def __repr__(self) -> str:
        return f"XdsTemplate({self.loadable=}, {self.is_python_source=}, {self.source=}, {self.jinja_variables=})"


class ProcessedTemplate:
    def __init__(
        self,
        resources: List[Dict[str, Any]],
        version_info: Optional[str],
    ) -> None:
        self.resources = resources
        self.version_info = version_info
        self._rendered: Optional[bytes] = None

    @property
    def version(self) -> str:
        return self.version_info or compute_hash(self.resources)

    @property
    def rendered(self) -> bytes:
        if self._rendered is None:
            result = JsonResponseClass(content="").render(
                content={
                    "version_info": self.version,
                    "resources": self.resources,
                }
            )
            self._rendered = result
        return self._rendered

    def deserialize_resources(self) -> List[Dict[str, Any]]:
        return self.resources


class Locality(BaseModel):
    region: Optional[str] = Field(None)
    zone: Optional[str] = Field(None)
    sub_zone: Optional[str] = Field(None)


class SemanticVersion(BaseModel):
    major_number: int = 0
    minor_number: int = 0
    patch: int = 0

    def __str__(self) -> str:
        return f"{self.major_number}.{self.minor_number}.{self.patch}"


class BuildVersion(BaseModel):
    version: SemanticVersion = SemanticVersion()
    metadata: Dict[str, Any] = {}


class Extension(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    version: Optional[BuildVersion] = None
    disabled: Optional[bool] = None


class Node(BaseModel):
    id: str = Field("-", title="Hostname")
    cluster: str = Field(
        ...,
        title="Envoy service-cluster",
        description="The ``--service-cluster`` configured by the Envoy client",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, title="Key:value metadata")
    locality: Locality = Field(Locality(), title="Locality")
    build_version: Optional[str] = Field(
        None,  # Optional in the v3 Envoy API
        title="Envoy build/release version string",
        description="Used to identify what version of Envoy the "
        "client is running, and what config to provide in response",
    )
    user_agent_name: str = "envoy"
    user_agent_version: str = ""
    user_agent_build_version: BuildVersion = BuildVersion()
    extensions: List[Extension] = []
    client_features: List[str] = []

    @property
    def common(self) -> Tuple[str, Optional[str], str, BuildVersion, Locality]:
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


class Resources(List[str]):
    """
    Acts like a regular list except it returns True
    for all membership tests when empty.
    """

    def __contains__(self, item: object) -> bool:
        if (
            len(self) == 0
        ):  # TODO: refactor to remove overriding __contains__; its being used in multiple places
            return True
        return super().__contains__(item)


class Status(BaseModel):
    code: int
    message: str
    details: List[Any]


def resources_factory() -> Resources:
    return Resources()


class DiscoveryRequest(BaseModel):
    node: Node = Field(..., title="Node information about the envoy proxy")
    version_info: str = Field(
        "0", title="The version of the envoy clients current configuration"
    )
    resource_names: Resources = Field(
        default_factory=resources_factory, title="List of requested resource names"
    )
    hide_private_keys: bool = False
    type_url: Optional[str] = Field(
        None, title="The corresponding type_url for the requested resource"
    )
    desired_controlplane: Optional[str] = Field(
        None, title="The host header provided in the Discovery Request"
    )
    error_detail: Optional[Status] = Field(
        None, title="Error details from the previous xDS request"
    )
    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def envoy_version(self) -> str:
        try:
            version = str(self.node.user_agent_build_version.version)
            assert version != "0.0.0"
        except AssertionError:
            try:
                build_version = self.node.build_version
                if build_version is None:
                    return "default"
                _, version, *_ = build_version.split("/")
            except (AttributeError, ValueError):
                # TODO: log/metric this?
                return "default"
        return version

    @property
    def resources(self) -> Resources:
        return Resources(self.resource_names)

    @property
    def uid(self) -> str:
        return compute_hash(
            self.resources,
            self.node.common,
            self.desired_controlplane,
        )

    @field_validator("resource_names", mode="before")
    @classmethod
    def validate_resources(cls, v: Union[Resources, List[str]]) -> Resources:
        return Resources(v)


class DiscoveryResponse(BaseModel):
    version_info: str = Field(
        ..., title="The version of the configuration in the response"
    )
    resources: List[Any] = Field(..., title="The requested configuration resources")


class SovereignAsgiConfig(BaseSettings):
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
    worker_tmp_dir: str = "/dev/shm"
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
        return {
            "bind": ":".join(map(str, [self.host, self.port])),
            "keepalive": self.keepalive,
            "reuse_port": self.reuse_port,
            "preload_app": self.preload_app,
            "loglevel": self.log_level,
            "timeout": self.worker_timeout,
            "threads": self.threads,
            "workers": self.workers,
            "worker_class": self.worker_class,
            "worker_tmp_dir": self.worker_tmp_dir,
            "graceful_timeout": self.graceful_timeout,
            "max_requests": self.max_requests,
            "max_requests_jitter": self.max_requests_jitter,
        }


class SovereignConfig(BaseSettings):
    sources: List[ConfiguredSource]
    templates: Dict[str, Dict[str, Union[str, Loadable]]]
    template_context: Dict[str, Any] = {}
    eds_priority_matrix: Dict[str, Dict[str, int]] = {}
    modifiers: List[str] = []
    global_modifiers: List[str] = []
    regions: List[str] = []
    statsd: StatsdConfig = StatsdConfig()
    auth_enabled: bool = Field(False, alias="SOVEREIGN_AUTH_ENABLED")
    auth_passwords: str = Field("", alias="SOVEREIGN_AUTH_PASSWORDS")
    encryption_key: str = Field("", alias="SOVEREIGN_ENCRYPTION_KEY")
    environment: str = Field("local", alias="SOVEREIGN_ENVIRONMENT")
    debug_enabled: bool = Field(False, alias="SOVEREIGN_DEBUG_ENABLED")
    sentry_dsn: str = Field("", alias="SOVEREIGN_SENTRY_DSN")
    node_match_key: str = Field("cluster", alias="SOVEREIGN_NODE_MATCH_KEY")
    node_matching: bool = Field(True, alias="SOVEREIGN_NODE_MATCHING")
    source_match_key: str = Field(
        "service_clusters", alias="SOVEREIGN_SOURCE_MATCH_KEY"
    )
    sources_refresh_rate: int = Field(30, alias="SOVEREIGN_SOURCES_REFRESH_RATE")
    cache_strategy: str = Field("context", alias="SOVEREIGN_CACHE_STRATEGY")
    refresh_context: bool = Field(False, alias="SOVEREIGN_REFRESH_CONTEXT")
    context_refresh_rate: Optional[int] = Field(
        None, alias="SOVEREIGN_CONTEXT_REFRESH_RATE"
    )
    context_refresh_cron: Optional[str] = Field(
        None, alias="SOVEREIGN_CONTEXT_REFRESH_CRON"
    )
    dns_hard_fail: bool = Field(False, alias="SOVEREIGN_DNS_HARD_FAIL")
    enable_application_logs: bool = Field(
        True, alias="SOVEREIGN_ENABLE_APPLICATION_LOGS"
    )
    enable_access_logs: bool = Field(True, alias="SOVEREIGN_ENABLE_ACCESS_LOGS")
    log_fmt: Optional[str] = Field("", alias="SOVEREIGN_LOG_FORMAT")
    ignore_empty_log_fields: bool = Field(False, alias="SOVEREIGN_LOG_IGNORE_EMPTY")
    discovery_cache: DiscoveryCacheConfig = DiscoveryCacheConfig()
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    @property
    def passwords(self) -> List[str]:
        return self.auth_passwords.split(",") or []

    def xds_templates(self) -> Dict[str, Dict[str, XdsTemplate]]:
        ret: Dict[str, Dict[str, XdsTemplate]] = {
            "__any__": {}
        }  # Special key to hold templates from all versions
        for version, templates in self.templates.items():
            loaded_templates = {
                _type: XdsTemplate(path=path) for _type, path in templates.items()
            }
            ret[str(version)] = loaded_templates
            ret["__any__"].update(loaded_templates)
        return ret

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        kwargs = [f"{k}={v}" for k, v in self.show().items()]
        return f"SovereignConfig({kwargs})"

    def show(self) -> Dict[str, Any]:
        safe_items = dict()
        for key, value in self.__dict__.items():
            if key in ["auth_passwords", "encryption_key", "passwords", "sentry_dsn"]:
                value = "redacted"
            safe_items[key] = value
        return safe_items


class TemplateSpecification(BaseModel):
    type: str
    spec: Loadable


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


class ContextConfiguration(BaseSettings):
    context: Dict[str, Loadable] = {}
    refresh: bool = Field(False, alias="SOVEREIGN_REFRESH_CONTEXT")
    refresh_rate: Optional[int] = Field(None, alias="SOVEREIGN_CONTEXT_REFRESH_RATE")
    refresh_cron: Optional[str] = Field(None, alias="SOVEREIGN_CONTEXT_REFRESH_CRON")
    refresh_num_retries: int = Field(3, alias="SOVEREIGN_CONTEXT_REFRESH_NUM_RETRIES")
    refresh_retry_interval_secs: int = Field(
        10, alias="SOVEREIGN_CONTEXT_REFRESH_RETRY_INTERVAL_SECS"
    )
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
    cache_strategy: CacheStrategy = Field(
        CacheStrategy.context, alias="SOVEREIGN_CACHE_STRATEGY"
    )
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )


class LegacyConfig(BaseSettings):
    regions: Optional[List[str]] = None
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
    def regions_is_set(cls, v: Optional[List[str]]) -> List[str]:
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


class SovereignConfigv2(BaseSettings):
    sources: List[ConfiguredSource]
    templates: Dict[str, List[TemplateSpecification]]
    source_config: SourcesConfiguration = SourcesConfiguration()
    modifiers: List[str] = []
    global_modifiers: List[str] = []
    template_context: ContextConfiguration = ContextConfiguration()
    matching: NodeMatching = NodeMatching()
    authentication: AuthConfiguration = AuthConfiguration()
    logging: LoggingConfiguration = LoggingConfiguration()
    statsd: StatsdConfig = StatsdConfig()
    sentry_dsn: SecretStr = Field(SecretStr(""), alias="SOVEREIGN_SENTRY_DSN")
    debug: bool = Field(False, alias="SOVEREIGN_DEBUG")
    legacy_fields: LegacyConfig = LegacyConfig()
    discovery_cache: DiscoveryCacheConfig = DiscoveryCacheConfig()
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    @property
    def passwords(self) -> List[str]:
        return self.authentication.auth_passwords.get_secret_value().split(",") or []

    def xds_templates(self) -> Dict[str, Dict[str, XdsTemplate]]:
        ret: Dict[str, Dict[str, XdsTemplate]] = {
            "__any__": {}
        }  # Special key to hold templates from all versions
        for version, template_specs in self.templates.items():
            loaded_templates = {
                template.type: XdsTemplate(path=template.spec)
                for template in template_specs
            }
            ret[str(version)] = loaded_templates
            ret["__any__"].update(loaded_templates)
        return ret

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        return f"SovereignConfigv2({self.model_dump()})"

    def show(self) -> Dict[str, Any]:
        return self.model_dump()

    @staticmethod
    def from_legacy_config(other: SovereignConfig) -> "SovereignConfigv2":
        new_templates = dict()
        for version, templates in other.templates.items():
            specs = list()
            for type, path in templates.items():
                if isinstance(path, str):
                    specs.append(
                        TemplateSpecification(
                            type=type, spec=Loadable.from_legacy_fmt(path)
                        )
                    )
                else:
                    # Just in case? Although this shouldn't happen
                    specs.append(TemplateSpecification(type=type, spec=path))
            new_templates[str(version)] = specs

        return SovereignConfigv2(
            sources=other.sources,
            templates=new_templates,
            source_config=SourcesConfiguration(
                refresh_rate=other.sources_refresh_rate,
                cache_strategy=CacheStrategy(other.cache_strategy),
            ),
            modifiers=other.modifiers,
            global_modifiers=other.global_modifiers,
            template_context=ContextConfiguration(
                context=ContextConfiguration.context_from_legacy(
                    other.template_context
                ),
                refresh=other.refresh_context,
                refresh_rate=other.context_refresh_rate,
                refresh_cron=other.context_refresh_cron,
            ),
            matching=NodeMatching(
                enabled=other.node_matching,
                source_key=other.source_match_key,
                node_key=other.node_match_key,
            ),
            authentication=AuthConfiguration(
                enabled=other.auth_enabled,
                auth_passwords=SecretStr(other.auth_passwords),
                encryption_key=SecretStr(other.encryption_key),
            ),
            logging=LoggingConfiguration(
                application_logs=ApplicationLogConfiguration(
                    enabled=other.enable_application_logs,
                ),
                access_logs=AccessLogConfiguration(
                    enabled=other.enable_access_logs,
                    log_fmt=other.log_fmt,
                    ignore_empty_fields=other.ignore_empty_log_fields,
                ),
            ),
            statsd=other.statsd,
            sentry_dsn=SecretStr(other.sentry_dsn),
            debug=other.debug_enabled,
            legacy_fields=LegacyConfig(
                regions=other.regions,
                eds_priority_matrix=other.eds_priority_matrix,
                dns_hard_fail=other.dns_hard_fail,
                environment=other.environment,
            ),
            discovery_cache=other.discovery_cache,
        )
