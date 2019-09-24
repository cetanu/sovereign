import logging
from functools import wraps
from sovereign import config

try:
    from datadog import statsd as statsd
except ImportError:
    if config.statsd.enabled:
        raise
    statsd = None


class StatsDProxy:
    def __init__(self, statsd_instance=None):
        self.statsd = statsd_instance

    def __getattr__(self, item):
        if self.statsd is not None:
            return getattr(self.statsd, item)
        try:
            return StatsdNoop
        except TypeError:
            return self.do_nothing

    def do_nothing(self, *args, **kwargs):
        pass


class StatsdNoop:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        pass

    def __call__(self, func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapped


def configure_statsd(module):
    if config.statsd.enabled:
        module.host = config.statsd.host
        module.port = config.statsd.port
        module.namespace = config.statsd.namespace
        module.use_ms = config.statsd.use_ms
        for tag, value in config.statsd.loaded_tags.items():
            module.constant_tags.extend([f'{tag}:{value}'])
    else:
        module = None
        statsd_logger = logging.getLogger('datadog.dogstatsd')
        statsd_logger.disabled = True
    return StatsDProxy(module)


stats = configure_statsd(module=statsd)
