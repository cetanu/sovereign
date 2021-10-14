"""
Discovery
---------

Functions used to render and return discovery responses to Envoy proxies.

The templates are configurable. `todo See ref:Configuration#Templates`
"""
import yaml
from yaml.parser import ParserError, ScannerError  # type: ignore
from enum import Enum
from typing import List, Dict, Any, Optional
from starlette.exceptions import HTTPException
from sovereign import XDS_TEMPLATES, config, logs, template_context
from sovereign.utils.version_info import compute_hash
from sovereign.schemas import XdsTemplate, DiscoveryRequest, ProcessedTemplate

try:
    import sentry_sdk

    SENTRY_INSTALLED = True
except ImportError:
    SENTRY_INSTALLED = False

try:
    default_templates = XDS_TEMPLATES["default"]
except KeyError:
    raise KeyError(
        "Your configuration should contain default templates. For more details, see "
        "https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/tutorial.html#create-templates "
    )

cache_strategy = config.source_config.cache_strategy

# Create an enum that bases all the available discovery types off what has been configured
discovery_types = (_type for _type in sorted(XDS_TEMPLATES["__any__"].keys()))
discovery_types_base: Dict[str, str] = {t: t for t in discovery_types}
# TODO: this needs to be typed somehow, but I have no idea how
DiscoveryTypes = Enum("DiscoveryTypes", discovery_types_base)  # type: ignore


def select_template(
    request: DiscoveryRequest,
    discovery_type: DiscoveryTypes,
    templates: Optional[Dict[str, Dict[str, XdsTemplate]]] = None,
) -> XdsTemplate:
    if templates is None:
        templates = XDS_TEMPLATES
    version = request.envoy_version
    selection = "default"
    for v in templates.keys():
        if version.startswith(v):
            selection = v
    selected_version = templates[selection]
    try:
        resource_type = str(discovery_type)
        return selected_version[resource_type]
    except KeyError:
        raise KeyError(
            f"Unable to get {discovery_type} for template "
            f'version "{selection}". Envoy client version: {version}'
        )


async def response(
    request: DiscoveryRequest, xds_type: DiscoveryTypes
) -> ProcessedTemplate:
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
    template: XdsTemplate = select_template(request, xds_type.value)
    context: Dict[str, Any] = template_context.get_context(request, template)

    config_version: Optional[str] = None
    if cache_strategy.context:
        config_version = compute_hash(
            context,
            template.checksum,
            request.node.common,
            request.resource_names,
            request.desired_controlplane,
        )
        if config_version == request.version_info:
            return ProcessedTemplate(
                version_info=config_version, resources=[], type_url=xds_type.value
            )

    context = dict(
        discovery_request=request,
        host_header=request.desired_controlplane,
        resource_names=request.resources,
        **context,
    )
    content = await template(**context)
    if not template.is_python_source:
        if not isinstance(content, str):
            raise RuntimeError(
                f"Attempting to deserialize potential non-string data: {content}"
            )
        content = deserialize_config(content)

    if cache_strategy.content:
        config_version = compute_hash(content)
        if config_version == request.version_info:
            return ProcessedTemplate(
                version_info=config_version, resources=[], type_url=xds_type.value
            )

    if not isinstance(content, dict):
        raise RuntimeError(f"Attempting to filter unstructured data: {content}")
    resources = filter_resources(content["resources"], request.resources)
    return ProcessedTemplate(
        resources=resources, type_url=request.type_url, version_info=config_version
    )


def deserialize_config(content: str) -> Dict[str, Any]:
    try:
        envoy_configuration = yaml.safe_load(content)
    except (ParserError, ScannerError) as e:
        logs.queue_log_fields(
            error=repr(e),
            YAML_CONTEXT=e.context,
            YAML_CONTEXT_MARK=e.context_mark,
            YAML_NOTE=e.note,
            YAML_PROBLEM=e.problem,
            YAML_PROBLEM_MARK=e.problem_mark,
        )

        if SENTRY_INSTALLED and config.sentry_dsn:
            sentry_sdk.capture_exception(e)

        raise HTTPException(
            status_code=500,
            detail="Failed to load configuration, there may be "
            "a syntax error in the configured templates. "
            "Please check Sentry if you have configured Sentry DSN",
        )
    if not isinstance(envoy_configuration, dict):
        raise RuntimeError(
            f"Deserialized configuration is of unexpected format: {envoy_configuration}"
        )
    return envoy_configuration


def filter_resources(
    generated: List[Dict[str, Any]], requested: List[str]
) -> List[Dict[str, Any]]:
    """
    If Envoy specifically requested a resource, this removes everything
    that does not match the name of the resource.
    If Envoy did not specifically request anything, every resource is retained.
    """
    return [resource for resource in generated if resource_name(resource) in requested]


def resource_name(resource: Dict[str, Any]) -> str:
    try:
        name = resource.get("name") or resource["cluster_name"]
        if isinstance(name, str):
            return name
    except KeyError:
        pass
    raise KeyError(
        f"Failed to determine the name or cluster_name of the following resource: {resource}"
    )
