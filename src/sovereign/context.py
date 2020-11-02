import sys
import schedule
from sovereign import config, XdsTemplate
from sovereign.config_loader import load
from sovereign.schemas import DiscoveryRequest
from sovereign.sources import extract_node_key, get_instances_for_node
from sovereign.statistics import stats
from sovereign.utils import crypto
from sovereign.utils.crypto import disabled_suite

template_context = {
    'crypto': crypto
}


def safe_context(request: DiscoveryRequest, template: XdsTemplate) -> dict:
    ret = build_template_context(
        node_value=extract_node_key(request.node),
        template=template,
    )
    # If the discovery request came from a mock, it will
    # typically contain this metadata key.
    # This means we should prevent any decryptable data
    # from ending up in the response.
    if request.hide_private_keys:
        ret['crypto'] = disabled_suite
    return ret


def build_template_context(node_value: str, template: XdsTemplate):
    """
    Creates context variables to be passed into either a jinja template,
    or as kwargs to a python template.
    """
    matches = get_instances_for_node(node_value=node_value)
    context = {**template_context}

    for scope, instances in matches.scopes.items():
        if scope == 'default':
            context['instances'] = instances
        else:
            context[scope] = instances

    if not template.is_python_source:
        for variable in list(context):
            if variable in template.jinja_variables():
                continue
            context.pop(variable, None)

    stats.set('discovery.context.bytes', sys.getsizeof(context))
    return context


def template_context_refresh():
    """ Modifies template_context in-place with new values """
    for k, v in config.template_context.items():
        template_context[k] = load(v)


# Initial setup
template_context_refresh()

if __name__ != '__main__' and config.refresh_context:  # pragma: no cover
    # This runs if the code was imported, as opposed to run directly
    schedule.every(config.context_refresh_rate).seconds.do(template_context_refresh)
