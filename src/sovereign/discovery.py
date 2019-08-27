"""
Discovery
---------

Functions used to render and return discovery responses to Envoy proxies.

The templates are configurable. `todo See ref:Configuration#Templates`
"""
import zlib
import yaml
from yaml.parser import ParserError
from sovereign import XDS_TEMPLATES, TEMPLATE_CONTEXT, statsd, config
from sovereign.sources import load_sources
from sovereign.dataclasses import XdsTemplate, DiscoveryRequest
from sovereign.utils.crypto import disabled_suite

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
    data: bytes = repr(args).encode()
    version_info = zlib.adler32(data)
    return str(version_info)


def template_context(request: DiscoveryRequest, debug=config.debug_enabled):
    return {
        'instances': load_sources(request.node.cluster, debug=debug),
        'resource_names': request.resource_names,
        'debug': debug,
        **TEMPLATE_CONTEXT
    }


async def response(request: DiscoveryRequest, xds, debug=config.debug_enabled, context=None) -> dict:
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
    :param debug: switch to control instance loading / exception raising
    :param context: optional alternative context for generation of templates
    :return: An envoy Discovery Response
    """
    metrics_tags = [
        f'xds_type:{xds}',
        f'partition:{request.node.cluster}'
    ]
    with statsd.timed('discovery.total_ms', use_ms=True, tags=metrics_tags):
        version = request.envoy_version
        template: XdsTemplate = XDS_TEMPLATES.get(version, default_templates)[xds]

        if context is None:
            context = template_context(request, debug)
        if request.node.metadata.get('hide_private_keys'):
            context['crypto'] = disabled_suite

        config_version = version_hash(context, template.checksum, request.node)
        if config_version == request.version_info:
            return {'version_info': config_version}

        with statsd.timed('discovery.render_ms', use_ms=True, tags=metrics_tags):
            rendered = await template.content.render_async(discovery_request=request, **context)
        try:
            configuration = yaml.load(rendered)
            configuration['version_info'] = config_version
            return configuration
        except ParserError:
            if debug:
                raise
            raise ParserError(
                'Failed to load configuration, there may be '
                'a syntax error in the configured templates. '
                f'xds_type:{xds} envoy_version:{version}'
            )
