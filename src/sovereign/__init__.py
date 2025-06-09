import sys
from contextvars import ContextVar
from importlib.metadata import version
from typing import Optional

from starlette.templating import Jinja2Templates

from sovereign.context import TemplateContext
from sovereign.logging.bootstrapper import LoggerBootstrapper
from sovereign.schemas import (
    config,
    SovereignAsgiConfig,
    migrate_configs,
)
from sovereign.sources import SourcePoller
from sovereign.statistics import configure_statsd
from sovereign.utils.crypto.crypto import CipherContainer
from sovereign.utils.resources import get_package_file

_request_id_ctx_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_ctx_var.get()


DIST_NAME = "sovereign"

__version__ = version(DIST_NAME)

html_templates = Jinja2Templates(
    directory=str(get_package_file(DIST_NAME, "templates"))
)

if sys.argv[0].endswith("sovereign"):
    migrate_configs()

asgi_config = SovereignAsgiConfig()
XDS_TEMPLATES = config.xds_templates()

stats = configure_statsd()
logs = LoggerBootstrapper(config)
application_logger = logs.application_logger.logger
poller = None
if config.sources is not None:
    if config.matching is not None:
        matching_enabled = config.matching.enabled
        node_key: Optional[str] = config.matching.node_key
        source_key: Optional[str] = config.matching.source_key
    else:
        matching_enabled = False
        node_key = None
        source_key = None
    poller = SourcePoller(
        sources=config.sources,
        matching_enabled=matching_enabled,
        node_match_key=node_key,
        source_match_key=source_key,
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
if poller is not None:
    poller.lazy_load_modifiers(config.modifiers)
    poller.lazy_load_global_modifiers(config.global_modifiers)
