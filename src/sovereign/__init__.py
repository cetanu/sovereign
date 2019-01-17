import os
from collections import defaultdict
from datadog import statsd
from sovereign import config_loader
from sovereign.logs import LOG

try:
    CONFIG_PATHS = os.getenv('SOVEREIGN_CONFIG').split(',')
except AttributeError:
    raise RuntimeError('No configuration specified via environment variable SOVEREIGN_CONFIG')

CONFIG = dict()
for path in CONFIG_PATHS:
    cfg = config_loader.load(path)
    CONFIG.update(cfg)

_templates = CONFIG['templates'].items()
_template_context = CONFIG.get('template_context', {}).items()

XDS_TEMPLATES = defaultdict(dict)
for version, templates in _templates:
    for _type, path in templates.items():
        XDS_TEMPLATES[version][_type] = config_loader.load(path)

TEMPLATE_CONTEXT = dict()
for key, value in _template_context:
    TEMPLATE_CONTEXT[key] = config_loader.load(value)

if CONFIG.get('statsd', {}).get('enabled'):
    statsd.host = CONFIG['statsd']['host']
    statsd.namespace = CONFIG['statsd'].get('namespace', 'sovereign')

DEBUG = bool(os.getenv('SOVEREIGN_DEBUG'))

ENVIRONMENT = os.getenv('SOVEREIGN_ENVIRONMENT_TYPE', os.getenv('MICROS_ENVTYPE', 'local'))

LOG.msg(
    event='startup',
    envtype=os.getenv('MICROS_ENVTYPE', os.getenv('SOVEREIGN_ENVIRONMENT_TYPE')),
    env=ENVIRONMENT,
    config=CONFIG_PATHS,
    context=_template_context,
    templates=_templates,
    is_debug=DEBUG
)
