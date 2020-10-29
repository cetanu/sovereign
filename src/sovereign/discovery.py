"""
Discovery
---------

Functions used to render and return discovery responses to Envoy proxies.

The templates are configurable. `todo See ref:Configuration#Templates`
"""
import yaml
from yaml.parser import ParserError, ScannerError
from enum import Enum
from starlette.exceptions import HTTPException
from sovereign import XDS_TEMPLATES, config
from sovereign.logs import LOG
from sovereign.context import safe_context
from sovereign.schemas import XdsTemplate, DiscoveryRequest, ProcessedTemplate

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None

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


def select_template(request: DiscoveryRequest, discovery_type: DiscoveryTypes, templates=None) -> XdsTemplate:
    if templates is None:
        templates = XDS_TEMPLATES
    version = request.envoy_version
    selection = 'default'
    for v in templates.keys():
        if version.startswith(v):
            selection = v
    selected_version = templates[selection]
    try:
        return selected_version[discovery_type]
    except KeyError:
        raise KeyError(f'Unable to get {discovery_type} for template version "{selection}". Envoy client version: {version}')


async def response(request: DiscoveryRequest, xds_type: DiscoveryTypes, host: str = 'none') -> ProcessedTemplate:
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
    template: XdsTemplate = select_template(request, xds_type)
    context: dict = safe_context(request, template)
    context = dict(
        discovery_request=request,
        host_header=host,
        resource_names=request.resources,
        **context
    )
    content = await template(**context)
    if not template.is_python_source:
        content = deserialize_config(content)
    resources = filter_resources(content['resources'], request.resources)
    return ProcessedTemplate(resources=resources, type_url=request.type_url)


def deserialize_config(content):
    try:
        envoy_configuration = yaml.safe_load(content)
    except (ParserError, ScannerError) as e:
        LOG.msg(
            error=repr(e),
            context=e.context,
            context_mark=e.context_mark,
            note=e.note,
            problem=e.problem,
            problem_mark=e.problem_mark,
        )

        if config.sentry_dsn and sentry_sdk:
            sentry_sdk.capture_exception(e)

        raise HTTPException(
            status_code=500,
            detail='Failed to load configuration, there may be '
                   'a syntax error in the configured templates. '
                   'Please check Sentry if you have configured Sentry DSN'

        )
    return envoy_configuration


def filter_resources(generated, requested):
    """
    If Envoy specifically requested a resource, this removes everything
    that does not match the name of the resource.
    If Envoy did not specifically request anything, every resource is retained.
    """
    return [
        resource
        for resource in generated
        if resource_name(resource) in requested
    ]


def resource_name(resource):
    return resource.get('name') or resource['cluster_name']
