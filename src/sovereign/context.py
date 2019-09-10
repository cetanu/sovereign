import schedule
from sovereign import config
from sovereign.utils import crypto
from sovereign.config_loader import load

template_context = {
    'crypto': crypto
}


def refresh():
    """ Modifies template_context in-place with new values """
    for k, v in config.template_context.items():
        template_context[k] = load(v)


# Initial setup
refresh()

if __name__ != '__main__' and config.refresh_context:
    schedule.every(config.context_refresh_rate).do(refresh)
