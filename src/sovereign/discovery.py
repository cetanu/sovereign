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
from starlette.exceptions import HTTPException
from sovereign import XDS_TEMPLATES, config
from sovereign.logs import LOG
from sovereign.statistics import stats
from sovereign.context import safe_context
from sovereign.schemas import XdsTemplate, DiscoveryRequest

try:
    default_templates = XDS_TEMPLATES['default']
except KeyError:
    raise KeyError(
        'Your configuration should contain default templates. For more details, see '
        'https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/tutorial.html#create-templates '
    )

# Create an enum that bases all the available discovery types off what has been configured
discovery_types = (_type for _type in sorted(XDS_TEMPLATES['__any__'].keys()))
# noinspection PyArgumentList
DiscoveryTypes = Enum('DiscoveryTypes', {t: t for t in discovery_types})


@stats.timed('discovery.version_hash_ms')
def version_hash(*args) -> str:
    """
    Creates a 'version hash' to be used in envoy Discovery Responses.
    """
    data: bytes = repr(args).encode()
    version_info = zlib.adler32(data) & 0xffffffff  # same numeric value across all py versions & platforms
    return str(version_info)


def load_template(request, type_) -> XdsTemplate:
    return config.select_template(request.envoy_version)[type_]


async def process_template(template, context):
    if template.is_python_source:
        return {'resources': list(template.code.call(**context))}
    else:
        return await template.content.render_async(**context)


async def response(request: DiscoveryRequest, xds_type: DiscoveryTypes, host: str = 'none'):
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
    :param host: the host header that was received from the envoy client
    :return: An envoy Discovery Response
    """
    template: XdsTemplate = load_template(request, xds_type)
    context: dict = safe_context(request, template)

    config_version = '0'
    if config.cache_strategy == 'context':
        config_version = version_hash(context, template.checksum, request.node.common, request.resources)
        if config_version == request.version_info:
            return {'version_info': config_version}

    content = await process_template(
        template=template,
        context=dict(
            discovery_request=request,
            host_header=host,
            resource_names=request.resources,
            **context
        )
    )

    # We can determine the version number before deserializing the YAML string into python
    if config.cache_strategy == 'content':
        config_version = version_hash(content)
        if config_version == request.version_info:
            return {'version_info': config_version}

    # This is the most expensive operation, I think, so it's performed as late as possible.
    if not template.is_python_source:
        content = deserialize_config(content)

    content['version_info'] = config_version
    return filter_resources(content, request.resources)


def deserialize_config(content):
    try:
        envoy_configuration = yaml.safe_load(content)
    except ParserError as e:
        LOG.msg(
            error=repr(e),
            context=e.context,
            context_mark=e.context_mark,
            note=e.note,
            problem=e.problem,
            problem_mark=e.problem_mark,
        )
        raise HTTPException(
            status_code=500,
            detail='Failed to load configuration, there may be '
                   'a syntax error in the configured templates.'
        )
    return envoy_configuration


def filter_resources(conf, requested):
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
