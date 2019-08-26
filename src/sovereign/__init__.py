import os
import quart.flask_patch
from datadog import statsd
from pkg_resources import get_distribution
from sovereign import config_loader
from sovereign.dataclasses import SovereignConfig, XdsTemplate
from sovereign.logs import LOG

__version__ = tuple(int(i) for i in get_distribution('sovereign').version.split('.'))


XDS_TEMPLATES = dict()
TEMPLATE_CONTEXT = dict()
CONFIG_FILE = dict()


def configure_statsd(statsd_, conf_):
    statsd_.host = conf_.host
    statsd_.port = conf_.port
    statsd_.namespace = conf_.namespace
    for tag, value in conf_.tags.items():
        statsd_.constant_tags.extend([f'{tag}:{value}'])
    return statsd_


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

    for k, v in config.template_context.items():
        TEMPLATE_CONTEXT[k] = config_loader.load(v)
    if 'crypto' not in TEMPLATE_CONTEXT:
        TEMPLATE_CONTEXT['crypto'] = config_loader.load('module://sovereign.utils.crypto')

    LOG.msg(
        event='startup',
        env=config.environment,
        config=CONFIG_PATHS,
        context=config.template_context,
        templates=config.templates,
        is_debug=config.debug_enabled
    )
