import schedule
from sovereign import config
from sovereign.utils import crypto
from sovereign.config_loader import load

template_context = {
    'crypto': crypto
}


def template_context_refresh():
    """ Modifies template_context in-place with new values """
    for k, v in config.template_context.items():
        template_context[k] = load(v)


# Initial setup
template_context_refresh()

if __name__ != '__main__' and config.refresh_context:  # pragma: no cover
    # This runs if the code was imported, as opposed to run directly
    schedule.every(config.context_refresh_rate).seconds.do(template_context_refresh)
