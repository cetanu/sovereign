import os
import logging
from datadog import statsd
from pkg_resources import get_distribution, resource_filename
from starlette.templating import Jinja2Templates
from sovereign import config_loader
from sovereign.utils.dictupdate import merge
from sovereign.schemas import SovereignConfig, XdsTemplate
from sovereign.logs import LOG

__versionstr__ = get_distribution('sovereign').version
__version__ = tuple(int(i) for i in __versionstr__.split('.'))

html_templates = Jinja2Templates(resource_filename('sovereign', 'templates'))

XDS_TEMPLATES = dict()
CONFIG_FILE = dict()


def configure_statsd(statsd_, conf_):
    statsd_.host = conf_.host
    statsd_.port = conf_.port
    statsd_.namespace = conf_.namespace
    for tag, value in conf_.loaded_tags.items():
        statsd_.constant_tags.extend([f'{tag}:{value}'])
    return statsd_


try:
    CONFIG_PATHS = os.getenv('SOVEREIGN_CONFIG').split(',')
except AttributeError:
    LOG.error('No configuration specified via environment variable SOVEREIGN_CONFIG')
else:
    for path in CONFIG_PATHS:
        CONFIG_FILE = merge(
            obj_a=CONFIG_FILE,
            obj_b=config_loader.load(path),
            merge_lists=True
        )

    config = SovereignConfig(**CONFIG_FILE)

    if config.statsd.enabled:
        statsd = configure_statsd(statsd, config.statsd)
    else:
        statsd_logger = logging.getLogger('datadog.dogstatsd')
        statsd_logger.disabled = True

    for version, templates in config.templates.items():
        XDS_TEMPLATES[version] = dict()
        for _type, path in templates.items():
            XDS_TEMPLATES[version][_type] = XdsTemplate(path=path)

    LOG.msg(
        event='startup',
        env=config.environment,
        config=CONFIG_PATHS,
        context=config.template_context,
        templates=config.templates,
        is_debug=config.debug_enabled
    )
