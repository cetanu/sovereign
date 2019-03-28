import os
from collections import defaultdict
from datadog import statsd
from sovereign import config_loader
from sovereign.logs import LOG

XDS_TEMPLATES = defaultdict(dict)
TEMPLATE_CONTEXT = dict()
DEBUG = bool(os.getenv('SOVEREIGN_DEBUG'))
ENVIRONMENT = os.getenv('SOVEREIGN_ENVIRONMENT_TYPE', os.getenv('MICROS_ENVTYPE', 'local'))
CONFIG = dict()

try:
    CONFIG_PATHS = os.getenv('SOVEREIGN_CONFIG').split(',')
except AttributeError:
    LOG.error('No configuration specified via environment variable SOVEREIGN_CONFIG')
else:
    for path in CONFIG_PATHS:
        cfg = config_loader.load(path)
        CONFIG.update(cfg)

    _templates = CONFIG['templates'].items()
    _template_context = CONFIG.get('template_context', {}).items()

    for version, templates in _templates:
        for _type, path in templates.items():
            XDS_TEMPLATES[version][_type] = config_loader.load(path)

    for key, value in _template_context:
        TEMPLATE_CONTEXT[key] = config_loader.load(value)

    if CONFIG.get('statsd', {}).get('enabled'):
        statsd.host = CONFIG['statsd']['host']
        statsd.namespace = CONFIG['statsd'].get('namespace', 'sovereign')

    NO_CHANGE_CODE = CONFIG.get('no_changes_response_code', 304)

    LOG.msg(
        event='startup',
        envtype=os.getenv('MICROS_ENVTYPE', os.getenv('SOVEREIGN_ENVIRONMENT_TYPE')),
        env=ENVIRONMENT,
        config=CONFIG_PATHS,
        context=_template_context,
        templates=_templates,
        is_debug=DEBUG
    )
