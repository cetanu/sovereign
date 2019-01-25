"""
Discovery
---------

Functions used to render and return discovery responses to Envoy proxies.

The templates are configurable. `todo See ref:Configuration#Templates`
"""
import hashlib
import yaml
from yaml.parser import ParserError
from sovereign import XDS_TEMPLATES, TEMPLATE_CONTEXT, DEBUG, statsd
from sovereign.decorators import envoy_authorization_required
from sovereign.sources import load_sources


def version_hash(config: dict) -> str:
    """
    Creates a 'version hash' to be used in envoy Discovery Responses.

    :param config: Any dictionary
    :return: 16 character hexadecimal string
    """
    config_string: bytes = repr(yaml.dump(config)).encode()
    return hashlib.sha256(config_string).hexdigest()


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
    partition = request['node']['cluster']
    context = {
        'instances': load_sources(partition, debug=debug),
        'resource_names': request.get('resource_names', []),
        'discovery_request': request,
        'debug': debug,
        **TEMPLATE_CONTEXT
    }
    metrics_tags = [
        f'xds_type:{xds}',
        f'partition:{partition}'
    ]
    if version not in XDS_TEMPLATES:
        version = 'default'
    template = XDS_TEMPLATES[version][xds]
    with statsd.timed('discovery.render_ms', use_ms=True, tags=metrics_tags):
        rendered = template.render(**context)
    try:
        configuration = yaml.load(rendered)
        configuration['version_info'] = version_hash(configuration)
        return configuration
    except ParserError:
        if debug:
            raise
        raise ParserError('Failed to render configuration')
