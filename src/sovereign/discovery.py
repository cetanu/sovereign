"""
Discovery
---------

Functions used to render and return discovery responses to Envoy proxies.

The templates are configurable. `todo See ref:Configuration#Templates`
"""
import yaml
from yaml.parser import ParserError
from sovereign import XDS_TEMPLATES, TEMPLATE_CONTEXT, DEBUG, statsd
from sovereign.decorators import envoy_authorization_required
from sovereign.sources import load_sources

try:
    default_templates = XDS_TEMPLATES['default']
except KeyError:
    raise KeyError(
        'Your configuration should contain default templates. For more details, see '
        'https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/tutorial.html#create-templates '
    )


@statsd.timed('discovery.version_hash_ms', use_ms=True)
def version_hash(*args) -> str:
    """
    Creates a 'version hash' to be used in envoy Discovery Responses.
    """
    return str(hash(repr(args)))


@envoy_authorization_required
def response(request, xds, version, debug=DEBUG) -> dict:
    """
    A Discovery **Request** typically looks something like:

    .. code-block:: json

        {
            "version_info": "0",
            "node": {
                "cluster": "T1",
                "build_version": "<revision hash>/<version>/Clean/RELEASE",
                "metadata": {
                    "auth": "..."
                }
            }
        }

    When we receive this, we give the client the latest configuration via a
    Discovery **Response** that looks something like this:

    .. code-block:: json

        {
            "version_info": "abcdef1234567890",
            "resources": []
        }

    The version_info is derived from :func:`sovereign.discovery.version_hash`

    :param request: An envoy Discovery Request
    :param xds: what type of XDS template to use when rendering
    :param version: what template version to render for (i.e. envoy 1.7.0, 1.8.0)
    :param debug: switch to control instance loading / exception raising
    :return: An envoy Discovery Response
    """
    cluster = request['node']['cluster']
    metrics_tags = [
        f'xds_type:{xds}',
        f'partition:{cluster}'
    ]
    with statsd.timed('discovery.total_ms', use_ms=True, tags=metrics_tags):
        context = {
            'instances': load_sources(cluster, debug=debug),
            'resource_names': request.get('resource_names', []),
            'debug': debug,
            **TEMPLATE_CONTEXT
        }
        template = XDS_TEMPLATES.get(version, default_templates)[xds]
        config_version = version_hash(context, template, request['node'])
        if config_version == request.get('version_info', '0'):
            return {'version_info': config_version}

        with statsd.timed('discovery.render_ms', use_ms=True, tags=metrics_tags):
            rendered = template.render(discovery_request=request, **context)
        try:
            configuration = yaml.load(rendered)
            configuration['version_info'] = config_version
            return configuration
        except ParserError:
            if debug:
                raise
            raise ParserError('Failed to render configuration')
