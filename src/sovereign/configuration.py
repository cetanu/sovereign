import os
from typing import Any, Mapping

from pydantic.error_wrappers import ValidationError

from sovereign.schemas import (
    SovereignAsgiConfig,
    SovereignConfig,
    SovereignConfigv2,
)
from sovereign.logging.bootstrapper import LoggerBootstrapper
from sovereign.statistics import configure_statsd
from sovereign.sources import SourcePoller
from sovereign.context import TemplateContext
from sovereign.utils.crypto import CipherContainer, create_cipher_suite
from sovereign import config_loader
from sovereign.utils.dictupdate import merge  # type: ignore


def parse_raw_configuration(path: str) -> Mapping[Any, Any]:
    ret: Mapping[Any, Any] = dict()
    for p in path.split(","):
        spec = config_loader.Loadable.from_legacy_fmt(p)
        ret = merge(obj_a=ret, obj_b=spec.load(), merge_lists=True)
    return ret


def load_sovereign_configuration() -> SovereignConfigv2:
    config_path = os.getenv("SOVEREIGN_CONFIG", "file:///etc/sovereign.yaml")
    try:
        return SovereignConfigv2(**parse_raw_configuration(config_path))
    except ValidationError:
        old_config = SovereignConfig(**parse_raw_configuration(config_path))
        return SovereignConfigv2.from_legacy_config(old_config)


CONFIG = load_sovereign_configuration()
ASGI_CONFIG = SovereignAsgiConfig()
XDS_TEMPLATES = CONFIG.xds_templates()

LOGS = LoggerBootstrapper(CONFIG)
STATS = configure_statsd(config=CONFIG.statsd)
FERNET_KEYS = CONFIG.authentication.encryption_key
ENCRYPTION_KEYS = FERNET_KEYS.get_secret_value().encode().split()
CIPHER_SUITE = CipherContainer(
    [
        create_cipher_suite(key=key, logger=LOGS.application_logger.logger)
        for key in ENCRYPTION_KEYS
    ]
)

POLLER = SourcePoller(
    sources=CONFIG.sources,
    matching_enabled=CONFIG.matching.enabled,
    node_match_key=CONFIG.matching.node_key,
    source_match_key=CONFIG.matching.source_key,
    source_refresh_rate=CONFIG.source_config.refresh_rate,
    logger=LOGS.application_logger.logger,
    stats=STATS,
)
TEMPLATE_CONTEXT = TemplateContext(
    refresh_rate=CONFIG.template_context.refresh_rate,
    refresh_cron=CONFIG.template_context.refresh_cron,
    refresh_num_retries=CONFIG.template_context.refresh_num_retries,
    refresh_retry_interval_secs=CONFIG.template_context.refresh_retry_interval_secs,
    configured_context=CONFIG.template_context.context,
    poller=POLLER,
    encryption_suite=CIPHER_SUITE,
    disabled_suite=create_cipher_suite(b"", LOGS.application_logger.logger),
    logger=LOGS.application_logger.logger,
    stats=STATS,
)
POLLER.lazy_load_modifiers(CONFIG.modifiers)
POLLER.lazy_load_global_modifiers(CONFIG.global_modifiers)
