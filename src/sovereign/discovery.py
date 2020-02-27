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
from starlette.exceptions import HTTPException
from sovereign import XDS_TEMPLATES
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

# Create an enum that bases all the available discovery types off what has been configured
discovery_types = (_type for _type in sorted(XDS_TEMPLATES['__any__'].keys()))
DiscoveryTypes = Enum('DiscoveryTypes', {t: t for t in discovery_types})


@stats.timed('discovery.version_hash_ms')
def version_hash(*args) -> str:
    """
    Creates a 'version hash' to be used in envoy Discovery Responses.
    """
    data: bytes = repr(args).encode()
    version_info = zlib.adler32(data)
    return str(version_info)


def make_context(request: DiscoveryRequest, template: XdsTemplate):
    """
    Creates context variables to be passed into either a jinja template,
    or as kwargs to a python template.
    """
    context = {
        'instances': match_node(request),
        'resource_names': request.resources,
        **template_context
    }

    # If the discovery request came from a mock, it will
    # typically contain this metadata key.
    # This means we should prevent any decryptable data
    # from ending up in the response.
    if request.node.metadata.get('hide_private_keys'):
        context['crypto'] = disabled_suite

    if template.is_python_source:
        return context
    else:
        # Jinja templates will be converted to an AST and then scanned for unused
        # variables, which reduces computation in cases where a lot of context
        # has been generated, but does not need to be checksum'd or rendered.
        template_ast = jinja_env.parse(template.source)
        used_variables = meta.find_undeclared_variables(template_ast)
        for key in list(context):
            if key in used_variables:
                continue
            context.pop(key, None)
        return context


async def response(request: DiscoveryRequest, xds_type: DiscoveryTypes):
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
    :param xds_type: what type of XDS template to use when rendering
    :return: An envoy Discovery Response
    """
    template: XdsTemplate = XDS_TEMPLATES.get(request.envoy_version, default_templates)[xds_type]
    context = make_context(request, template)

    config_version = version_hash(context, template.checksum, request.node.common, request.resources)
    if config_version == request.version_info:
        return {'version_info': config_version}

    if template.is_python_source:
        envoy_configuration = {
            'resources': list(template.code.call(discovery_request=request, **context)),
            'version_info': config_version
        }
    else:
        rendered = await template.content.render_async(discovery_request=request, **context)
        try:
            envoy_configuration = yaml.safe_load(rendered)
            envoy_configuration['version_info'] = config_version
        except ParserError:
            raise HTTPException(
                status_code=500,
                detail='Failed to load configuration, there may be '
                       'a syntax error in the configured templates.'
            )
    return remove_unwanted_resources(envoy_configuration, request.resources)


def remove_unwanted_resources(conf, requested):
    """
    If Envoy specifically requested a resource, this removes everything
    that does not match the name of the resource.
    If Envoy did not specifically request anything, every resource is retained.
    """
    ret = dict()
    ret['version_info'] = conf['version_info']
    ret['resources'] = [
        resource
        for resource in conf.get('resources', [])
        if resource_name(resource) in requested
    ]
    return ret


def resource_name(resource):
    return resource.get('name') or resource['cluster_name']
