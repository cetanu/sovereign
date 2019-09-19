from random import randint
from functools import wraps
from datetime import timedelta
from cachelib import SimpleCache
from sovereign import statsd, LOG


cache = SimpleCache()


def memoize(timeout, jitter=0):
    """
    Decorator to cache a function by name/args

    :param timeout: How long to keep the result
    :param jitter: Randomize the timeout by this many seconds
    """
    if isinstance(timeout, timedelta):
        timeout = timeout.seconds

    timeout += randint(-jitter/2, jitter)

    def decorator(decorated):
        @wraps(decorated)
        def wrapper(*args, **kwargs):
            key = f'{decorated.__name__}{args}{kwargs}'
            ret = cache.get(key)
            metrics_tags = [
                f'function:{decorated.__name__}'
            ]
            if ret is None:
                statsd.increment('cache.miss', tags=metrics_tags)
                ret = decorated(*args, **kwargs)
                try:
                    cache.set(key, ret, timeout=timeout)
                except AttributeError:
                    statsd.increment('cache.fail', tags=metrics_tags)
                    LOG.msg(event='failed to write result to cache', level='warn', key=key)
            else:
                statsd.increment('cache.hit', tags=metrics_tags)
            return ret
        return wrapper
    return decorator
