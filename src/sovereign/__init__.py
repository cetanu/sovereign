import os
import zlib
import quart.flask_patch
from collections import defaultdict
from datadog import statsd
from pkg_resources import get_distribution
from sovereign import config_loader
from sovereign.logs import LOG

__version__ = get_distribution('sovereign').version


XDS_TEMPLATES = defaultdict(dict)
TEMPLATE_CONTEXT = dict()
DEBUG = bool(os.getenv('SOVEREIGN_DEBUG'))
ENVIRONMENT = os.getenv('SOVEREIGN_ENVIRONMENT_TYPE', os.getenv('MICROS_ENVTYPE', 'local'))
SENTRY_DSN = os.getenv('SOVEREIGN_SENTRY_DSN')
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
        XDS_TEMPLATES[version]['checksums'] = dict()
        for _type, path in templates.items():
            template = config_loader.load(path)
            XDS_TEMPLATES[version][_type] = template
            if 'jinja' in path:
                # The Jinja2 template serializer does not properly set a name
                # for the loaded template.
                # The repr for the template prints out as the memory address
                # This makes it really hard to generate a consistent version_info string
                # in rendered configuration.
                # For this reason, we re-load the template as a string instead, and create a checksum.
                new_path = path.replace('+jinja', '+string')
                template_source = config_loader.load(new_path)
                XDS_TEMPLATES[version]['checksums'][_type] = zlib.adler32(template_source.encode())
            else:
                # The only other supported serializers are string, yaml, and json
                # So it should be safe to create this checksum off
                XDS_TEMPLATES[version]['checksums'][_type] = zlib.adler32(str(template))

    for key, value in _template_context:
        TEMPLATE_CONTEXT[key] = config_loader.load(value)

    if CONFIG.get('statsd', {}).get('enabled'):
        statsd.host = CONFIG['statsd']['host']
        statsd.namespace = CONFIG['statsd'].get('namespace', 'sovereign')
        for tag, value in CONFIG['statsd'].get('tags', {}).items():
            value = config_loader.load(value)
            statsd.constant_tags.extend([f'{tag}:{value}'])

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
