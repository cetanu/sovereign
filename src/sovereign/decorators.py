import gzip
from random import randint
from functools import wraps
from datetime import timedelta
from quart import after_this_request, request, Response
from quart.datastructures import HeaderSet
from cachelib import SimpleCache
from sovereign import statsd


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
                cache.set(key, ret, timeout=timeout)
            else:
                statsd.increment('cache.hit', tags=metrics_tags)
            return ret
        return wrapper
    return decorator


def gzcompress(level=2, valid_codes=range(200, 304)):
    """
    Gzip compression decorator from : http://flask.pocoo.org/snippets/122/

    Modified to work with Quart
    Also added configurable compression level & status codes

    Unfortunately does not work with Envoy since it doesn't send gzip related headers
    """
    def decorator(f):
        @wraps(f)
        async def wrapper(*args, **kwargs):
            @after_this_request
            async def compress(response: Response) -> Response:
                accept_encoding = request.headers.get('Accept-Encoding', '').lower()

                if 'gzip' not in accept_encoding:
                    return response

                if response.status_code not in valid_codes or response.content_encoding:
                    return response

                data = await response.get_data()
                output = gzip.compress(data, compresslevel=level)

                response.set_data(output)
                response.content_encoding = 'gzip'
                response.vary = HeaderSet.from_header('Accept-Encoding')
                return response

            return await f(*args, **kwargs)
        return wrapper
    return decorator
