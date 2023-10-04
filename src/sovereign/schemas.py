from os import getenv
import warnings
import multiprocessing
from collections import defaultdict
from enum import Enum
from pydantic import (
    BaseModel,
    Field,
    BaseSettings,
    SecretStr,
    validator,
    root_validator,
)
from typing import List, Any, Dict, Union, Optional, Tuple, Type
from types import ModuleType
from jinja2 import meta, Template
from fastapi.responses import JSONResponse
from sovereign.config_loader import jinja_env, Serialization, Protocol, Loadable
from sovereign.utils.version_info import compute_hash
from croniter import croniter, CroniterBadCronError

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

    @validator("host", pre=True)
    def load_host(cls, v: str) -> Any:
        return Loadable.from_legacy_fmt(v).load()

    @validator("port", pre=True)
    def load_port(cls, v: Union[int, str]) -> Any:
        if isinstance(v, int):
            return v
        elif isinstance(v, str):
            return Loadable.from_legacy_fmt(v).load()
        else:
            raise ValueError(f"Received an invalid port: {v}")

    @validator("tags", pre=True)
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

    @root_validator
    def set_default_protocol(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        secure = values.get("secure")
        if secure:
            values["protocol"] = "rediss://"
        return values

    @root_validator
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
        self.is_python_source = self.loadable.protocol == Protocol.python
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
            self.loadable.protocol = Protocol("inline")
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
    region: str = Field(None)
    zone: str = Field(None)
    sub_zone: str = Field(None)


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
    locality: Locality = Field(Locality(), title="Locality")  # type: ignore
    build_version: str = Field(
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
    def common(self) -> Tuple[str, str, str, BuildVersion, Locality]:
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
        if len(self) == 0:
            return True
        return item in list(self)


class Status(BaseModel):
    code: int
    message: str
    details: List[Any]


class DiscoveryRequest(BaseModel):
    node: Node = Field(..., title="Node information about the envoy proxy")
    version_info: str = Field(
        "0", title="The version of the envoy clients current configuration"
    )
    resource_names: Resources = Field(
        Resources(), title="List of requested resource names"
    )
    hide_private_keys: bool = False
    type_url: Optional[str] = Field(
        None, title="The corresponding type_url for the requested resource"
    )
    desired_controlplane: str = Field(
        None, title="The host header provided in the Discovery Request"
    )
    error_detail: Status = Field(
        None, title="Error details from the previous xDS request"
    )

    @property
    def envoy_version(self) -> str:
        try:
            version = str(self.node.user_agent_build_version.version)
            assert version != "0.0.0"
        except AssertionError:
            try:
                build_version = self.node.build_version
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


class DiscoveryResponse(BaseModel):
    version_info: str = Field(
        ..., title="The version of the configuration in the response"
    )
    resources: List[Any] = Field(..., title="The requested configuration resources")


class SovereignAsgiConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8080
    keepalive: int = 5
    workers: int = multiprocessing.cpu_count() * 2 + 1
    threads: int = 1
    reuse_port: bool = True
    preload_app: bool = True
    log_level: str = "warning"
    worker_class: str = "uvicorn.workers.UvicornWorker"
    worker_timeout: int = 30
    worker_tmp_dir: str = "/dev/shm"
    graceful_timeout: int = worker_timeout * 2

    class Config:
        fields = {
            "host": {"env": "SOVEREIGN_HOST"},
            "port": {"env": "SOVEREIGN_PORT"},
            "keepalive": {"env": "SOVEREIGN_KEEPALIVE"},
            "workers": {"env": "SOVEREIGN_WORKERS"},
            "threads": {"env": "SOVEREIGN_THREADS"},
            "preload_app": {"env": "SOVEREIGN_PRELOAD"},
            "worker_timeout": {"env": "SOVEREIGN_WORKER_TIMEOUT"},
        }

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
        }


class SovereignConfig(BaseSettings):
    sources: List[ConfiguredSource]
    templates: Dict[str, Dict[str, Union[str, Loadable]]]
    template_context: Dict[str, Any] = {}
    eds_priority_matrix: Dict[str, Dict[str, str]] = {}
    modifiers: List[str] = []
    global_modifiers: List[str] = []
    regions: List[str] = []
    statsd: StatsdConfig = StatsdConfig()
    auth_enabled: bool = False
    auth_passwords: str = ""
    encryption_key: str = ""
    environment: str = "local"
    debug_enabled: bool = False
    sentry_dsn: str = ""
    node_match_key: str = "cluster"
    node_matching: bool = True
    source_match_key: str = "service_clusters"
    sources_refresh_rate: int = 30
    cache_strategy: str = "context"
    refresh_context: bool = False
    context_refresh_rate: Optional[int]
    context_refresh_cron: Optional[str]
    dns_hard_fail: bool = False
    enable_application_logs: bool = True
    enable_access_logs: bool = True
    log_fmt: Optional[str] = ""
    ignore_empty_log_fields: bool = False
    discovery_cache: DiscoveryCacheConfig = DiscoveryCacheConfig()

    class Config:
        fields = {
            "auth_enabled": {"env": "SOVEREIGN_AUTH_ENABLED"},
            "auth_passwords": {"env": "SOVEREIGN_AUTH_PASSWORDS"},
            "encryption_key": {"env": "SOVEREIGN_ENCRYPTION_KEY"},
            "environment": {"env": "SOVEREIGN_ENVIRONMENT"},
            "debug_enabled": {"env": "SOVEREIGN_DEBUG_ENABLED"},
            "sentry_dsn": {"env": "SOVEREIGN_SENTRY_DSN"},
            "node_match_key": {"env": "SOVEREIGN_NODE_MATCH_KEY"},
            "node_matching": {"env": "SOVEREIGN_NODE_MATCHING"},
            "source_match_key": {"env": "SOVEREIGN_SOURCE_MATCH_KEY"},
            "sources_refresh_rate": {"env": "SOVEREIGN_SOURCES_REFRESH_RATE"},
            "cache_strategy": {"env": "SOVEREIGN_CACHE_STRATEGY"},
            "refresh_context": {"env": "SOVEREIGN_REFRESH_CONTEXT"},
            "context_refresh_rate": {"env": "SOVEREIGN_CONTEXT_REFRESH_RATE"},
            "context_refresh_cron": {"env": "SOVEREIGN_CONTEXT_REFRESH_CRON"},
            "dns_hard_fail": {"env": "SOVEREIGN_DNS_HARD_FAIL"},
            "enable_application_logs": {"env": "SOVEREIGN_ENABLE_APPLICATION_LOGS"},
            "enable_access_logs": {"env": "SOVEREIGN_ENABLE_ACCESS_LOGS"},
            "log_fmt": {"env": "SOVEREIGN_LOG_FORMAT"},
            "ignore_empty_fields": {"env": "SOVEREIGN_LOG_IGNORE_EMPTY"},
        }

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
    enabled: bool = True
    source_key: str = "service_clusters"
    node_key: str = "cluster"

    class Config:
        fields = {
            "enabled": {"env": "SOVEREIGN_NODE_MATCHING_ENABLED"},
            "source_key": {"env": "SOVEREIGN_SOURCE_MATCH_KEY"},
            "node_key": {"env": "SOVEREIGN_NODE_MATCH_KEY"},
        }


class AuthConfiguration(BaseSettings):
    enabled: bool = False
    auth_passwords: SecretStr = SecretStr("")
    encryption_key: SecretStr = SecretStr("")

    class Config:
        fields = {
            "enabled": {"env": "SOVEREIGN_AUTH_ENABLED"},
            "auth_passwords": {"env": "SOVEREIGN_AUTH_PASSWORDS"},
            "encryption_key": {"env": "SOVEREIGN_ENCRYPTION_KEY"},
        }


class ApplicationLogConfiguration(BaseSettings):
    enabled: bool = False
    log_fmt: Optional[str] = None
    # currently only support /dev/stdout as JSON

    class Config:
        fields = {
            "enabled": {"env": "SOVEREIGN_ENABLE_APPLICATION_LOGS"},
            "log_fmt": {"env": "SOVEREIGN_APPLICATION_LOG_FORMAT"},
        }


class AccessLogConfiguration(BaseSettings):
    enabled: bool = True
    log_fmt: Optional[str] = None
    ignore_empty_fields: bool = False

    class Config:
        fields = {
            "enabled": {"env": "SOVEREIGN_ENABLE_ACCESS_LOGS"},
            "log_fmt": {"env": "SOVEREIGN_LOG_FORMAT"},
            "ignore_empty_fields": {"env": "SOVEREIGN_LOG_IGNORE_EMPTY"},
        }


class LoggingConfiguration(BaseSettings):
    application_logs: ApplicationLogConfiguration = ApplicationLogConfiguration()
    access_logs: AccessLogConfiguration = AccessLogConfiguration()


class ContextConfiguration(BaseSettings):
    context: Dict[str, Loadable] = {}
    refresh: bool = False
    refresh_rate: Optional[int] = None
    refresh_cron: Optional[str] = None
    refresh_num_retries: int = 3
    refresh_retry_interval_secs: int = 10

    @staticmethod
    def context_from_legacy(context: Dict[str, str]) -> Dict[str, Loadable]:
        ret = dict()
        for key, value in context.items():
            ret[key] = Loadable.from_legacy_fmt(value)
        return ret

    @root_validator(pre=False)
    def validate_single_use_refresh_method(
        cls, values: Dict[str, Any]
    ) -> Dict[str, Any]:
        refresh_rate = values.get("refresh_rate")
        refresh_cron = values.get("refresh_cron")

        if (refresh_rate is not None) and (refresh_cron is not None):
            raise RuntimeError(
                f"Only one of SOVEREIGN_CONTEXT_REFRESH_RATE or SOVEREIGN_CONTEXT_REFRESH_CRON can be defined. Got {refresh_rate=} and {refresh_cron=}"
            )
        return values

    @root_validator
    def set_default_refresh_rate(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        refresh_rate = values.get("refresh_rate")
        refresh_cron = values.get("refresh_cron")

        if (refresh_rate is None) and (refresh_cron is None):
            values["refresh_rate"] = 3600
        return values

    @validator("refresh_cron")
    def validate_refresh_cron(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not croniter.is_valid(v):
            raise CroniterBadCronError(f"'{v}' is not a valid cron expression")
        return v

    class Config:
        fields = {
            "refresh": {"env": "SOVEREIGN_REFRESH_CONTEXT"},
            "refresh_rate": {"env": "SOVEREIGN_CONTEXT_REFRESH_RATE"},
            "refresh_cron": {"env": "SOVEREIGN_CONTEXT_REFRESH_CRON"},
            "refresh_num_retries": {"env": "SOVEREIGN_CONTEXT_REFRESH_NUM_RETRIES"},
            "refresh_retry_interval_secs": {
                "env": "SOVEREIGN_CONTEXT_REFRESH_RETRY_INTERVAL_SECS"
            },
        }


class SourcesConfiguration(BaseSettings):
    refresh_rate: int = 30
    cache_strategy: CacheStrategy = CacheStrategy.context

    class Config:
        fields = {
            "refresh_rate": {"env": "SOVEREIGN_SOURCES_REFRESH_RATE"},
            "cache_strategy": {"env": "SOVEREIGN_CACHE_STRATEGY"},
        }


class LegacyConfig(BaseSettings):
    regions: Optional[List[str]] = None
    eds_priority_matrix: Optional[Dict[str, Dict[str, str]]] = None
    dns_hard_fail: Optional[bool] = None
    environment: Optional[str] = None

    @validator("regions")
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

    @validator("eds_priority_matrix")
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

    @validator("dns_hard_fail")
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

    @validator("environment")
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

    class Config:
        fields = {
            "dns_hard_fail": {"env": "SOVEREIGN_DNS_HARD_FAIL"},
            "environment": {"env": "SOVEREIGN_ENVIRONMENT"},
        }


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
    sentry_dsn: SecretStr = SecretStr("")
    debug: bool = False
    legacy_fields: LegacyConfig = LegacyConfig()
    discovery_cache: DiscoveryCacheConfig = DiscoveryCacheConfig()

    class Config:
        fields = {
            "sentry_dsn": {"env": "SOVEREIGN_SENTRY_DSN"},
            "debug": {"env": "SOVEREIGN_DEBUG"},
        }

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
        return f"SovereignConfigv2({self.dict()})"

    def show(self) -> Dict[str, Any]:
        return self.dict()

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
