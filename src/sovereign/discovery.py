"""
Discovery
---------

Functions used to render and return discovery responses to Envoy proxies.

The templates are configurable. `todo See ref:Configuration#Templates`
"""
import zlib
import yaml
from yaml.parser import ParserError
from enum import Enum
from jinja2 import meta
from sovereign import XDS_TEMPLATES, config
from sovereign.statistics import stats
from sovereign.context import template_context
from sovereign.sources import match_node
from sovereign.config_loader import jinja_env
from sovereign.schemas import XdsTemplate, DiscoveryRequest
from sovereign.utils.crypto import disabled_suite

try:
    default_templates = XDS_TEMPLATES['default']
except KeyError:
    raise KeyError(
        'Your configuration should contain default templates. For more details, see '
        'https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/tutorial.html#create-templates '
    )


discovery_types = list(XDS_TEMPLATES['default'].keys())
DiscoveryTypes = Enum('DiscoveryTypes', {t: t for t in discovery_types})


@stats.timed('discovery.version_hash_ms')
def version_hash(*args) -> str:
    """
    Creates a 'version hash' to be used in envoy Discovery Responses.
    """
    data: bytes = repr(args).encode()
    version_info = zlib.adler32(data)
    return str(version_info)


def make_context(request: DiscoveryRequest, debug=config.debug_enabled):
    return {
        'instances': match_node(request),
        'resource_names': request.resources,
        'debug': debug,
        **template_context
    }


async def response(request: DiscoveryRequest, xds, debug=config.debug_enabled):
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
    with stats.timed('discovery.total_ms', tags=metrics_tags):
        context = make_context(request, debug)
        if request.node.metadata.get('hide_private_keys'):
            context['crypto'] = disabled_suite

        template: XdsTemplate = XDS_TEMPLATES.get(request.envoy_version, default_templates)[xds]
        template_ast = jinja_env.parse(template.source)
        used_variables = meta.find_undeclared_variables(template_ast)
        unused_variables = [key for key in list(context)
                            if key not in used_variables]

        for key in unused_variables:
            context.pop(key, None)

        config_version = version_hash(
            context,
            template.checksum,
            request.node.cluster,
            request.node.build_version,
            request.node.locality,
        )
        if config_version == request.version_info:
            return {'version_info': config_version}

        with stats.timed('discovery.render_ms', tags=metrics_tags):
            rendered = await template.content.render_async(discovery_request=request, **context)
        return parse_envoy_configuration(rendered, config_version, request, xds, debug)


def parse_envoy_configuration(template_output, version_info, request, request_type, debug=config.debug_enabled):
    try:
        resources = yaml.safe_load(template_output)['resources']
    except ParserError:
        if debug:
            raise
        raise ParserError(
            'Failed to load configuration, there may be '
            'a syntax error in the configured templates. '
            f'xds_type:{request_type} envoy_version:{request.envoy_version}'
        )
    configuration = dict()
    configuration['version_info'] = version_info
    configuration['resources'] = [
        resource
        for resource in resources
        if resource_name(resource) in request.resources
    ]
    return configuration


def resource_name(resource):
    return resource.get('name') or resource['cluster_name']
