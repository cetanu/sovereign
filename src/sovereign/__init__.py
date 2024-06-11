import os
from contextvars import ContextVar
from importlib.metadata import version
from typing import Any, Mapping, Type

from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.templating import Jinja2Templates

from sovereign import config_loader
from sovereign.context import TemplateContext
from sovereign.logging.bootstrapper import LoggerBootstrapper
from sovereign.schemas import SovereignAsgiConfig, SovereignConfig, SovereignConfigv2
from sovereign.sources import SourcePoller
from sovereign.statistics import configure_statsd
from sovereign.utils.crypto.crypto import CipherContainer
from sovereign.utils.dictupdate import merge  # type: ignore
from sovereign.utils.resources import get_package_file

json_response_class: Type[JSONResponse] = JSONResponse
try:
    import orjson
    from fastapi.responses import ORJSONResponse

    json_response_class = ORJSONResponse
except ImportError:
    try:
        import ujson
        from fastapi.responses import UJSONResponse

        json_response_class = UJSONResponse
    except ImportError:
        pass


def parse_raw_configuration(path: str) -> Mapping[Any, Any]:
    ret: Mapping[Any, Any] = dict()
    for p in path.split(","):
        spec = config_loader.Loadable.from_legacy_fmt(p)
        ret = merge(obj_a=ret, obj_b=spec.load(), merge_lists=True)
    return ret


_request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_ctx_var.get()


DIST_NAME = "sovereign"

__version__ = version(DIST_NAME)
config_path = os.getenv("SOVEREIGN_CONFIG", "file:///etc/sovereign.yaml")

html_templates = Jinja2Templates(
    directory=str(get_package_file(DIST_NAME, "templates"))
)

try:
    config = SovereignConfigv2(**parse_raw_configuration(config_path))
except ValidationError:
    old_config = SovereignConfig(**parse_raw_configuration(config_path))
    config = SovereignConfigv2.from_legacy_config(old_config)
asgi_config = SovereignAsgiConfig()
XDS_TEMPLATES = config.xds_templates()

logs = LoggerBootstrapper(config)
application_logger = logs.application_logger.logger

stats = configure_statsd(config=config.statsd)
poller = SourcePoller(
    sources=config.sources,
    matching_enabled=config.matching.enabled,
    node_match_key=config.matching.node_key,
    source_match_key=config.matching.source_key,
    source_refresh_rate=config.source_config.refresh_rate,
    logger=application_logger,
    stats=stats,
)

encryption_configs = config.authentication.encryption_configs
server_cipher_container = CipherContainer.from_encryption_configs(
    encryption_configs, logger=application_logger
)

template_context = TemplateContext(
    refresh_rate=config.template_context.refresh_rate,
    refresh_cron=config.template_context.refresh_cron,
    refresh_num_retries=config.template_context.refresh_num_retries,
    refresh_retry_interval_secs=config.template_context.refresh_retry_interval_secs,
    configured_context=config.template_context.context,
    poller=poller,
    encryption_suite=server_cipher_container,
    logger=application_logger,
    stats=stats,
)
poller.lazy_load_modifiers(config.modifiers)
poller.lazy_load_global_modifiers(config.global_modifiers)
