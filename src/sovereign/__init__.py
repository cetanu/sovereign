import os
from contextvars import ContextVar
from typing import Type, Any, Mapping
from pkg_resources import get_distribution, resource_filename

from fastapi.responses import JSONResponse
from starlette.templating import Jinja2Templates

from sovereign.schemas import (
    SovereignAsgiConfig,
    SovereignConfig,
    SovereignConfigv2,
)
from sovereign import config_loader
from sovereign.logs import LoggerBootstrapper
from sovereign.statistics import configure_statsd
from sovereign.utils.dictupdate import merge  # type: ignore
from sovereign.sources import SourcePoller


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


__version__ = get_distribution("sovereign").version
config_path = os.getenv("SOVEREIGN_CONFIG", "file:///etc/sovereign.yaml")
html_templates = Jinja2Templates(resource_filename("sovereign", "templates"))
old_config = SovereignConfig(**parse_raw_configuration(config_path))
config = SovereignConfigv2.from_legacy_config(old_config)
asgi_config = SovereignAsgiConfig()
XDS_TEMPLATES = config.xds_templates()

logs = LoggerBootstrapper(config)
stats = configure_statsd(config=config.statsd)
poller = SourcePoller(
    sources=config.sources,
    matching_enabled=config.matching.enabled,
    node_match_key=config.matching.node_key,
    source_match_key=config.matching.source_key,
    source_refresh_rate=config.source_config.refresh_rate,
    logger=logs.application_log,
    stats=stats,
)
