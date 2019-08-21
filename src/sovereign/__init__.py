import os
import quart.flask_patch
from datadog import statsd
from pkg_resources import get_distribution
from sovereign import config_loader
from sovereign.dataclasses import SovereignConfig, XdsTemplate
from sovereign.logs import LOG

__version__ = get_distribution('sovereign').version


XDS_TEMPLATES = dict()
TEMPLATE_CONTEXT = dict()
DEBUG = bool(os.getenv('SOVEREIGN_DEBUG'))
ENVIRONMENT = os.getenv('SOVEREIGN_ENVIRONMENT_TYPE', os.getenv('MICROS_ENVTYPE', 'local'))
SENTRY_DSN = os.getenv('SOVEREIGN_SENTRY_DSN')
CONFIG_FILE = dict()


def configure_statsd(statsd_instance, statsd_config):
    statsd_instance.host = statsd_config.host
    statsd_instance.namespace = statsd_config.namespace
    for tag, value in statsd_config.tags.items():
        statsd_instance.constant_tags.extend([f'{tag}:{value}'])
    return statsd_instance


try:
    CONFIG_PATHS = os.getenv('SOVEREIGN_CONFIG').split(',')
except AttributeError:
    LOG.error('No configuration specified via environment variable SOVEREIGN_CONFIG')
else:
    for path in CONFIG_PATHS:
        cfg = config_loader.load(path)
        CONFIG_FILE.update(cfg)

    config = SovereignConfig(**CONFIG_FILE)

    if config.metrics.enabled:
        statsd = configure_statsd(statsd, config.metrics)

    for version, templates in config.templates.items():
        XDS_TEMPLATES[version] = dict()
        for _type, path in templates.items():
            XDS_TEMPLATES[version][_type] = XdsTemplate(path=path)

    for key, value in config.template_context.items():
        TEMPLATE_CONTEXT[key] = config_loader.load(value)

    LOG.msg(
        event='startup',
        envtype=os.getenv('MICROS_ENVTYPE', os.getenv('SOVEREIGN_ENVIRONMENT_TYPE')),
        env=ENVIRONMENT,
        config=CONFIG_PATHS,
        context=config.template_context,
        templates=config.templates,
        is_debug=DEBUG
    )
