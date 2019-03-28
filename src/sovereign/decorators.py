import gzip
from functools import wraps
from datetime import timedelta
from quart import after_this_request, request, Response
from quart.datastructures import HeaderSet
from werkzeug.exceptions import BadRequest, Unauthorized
from cachelib import SimpleCache
from sovereign import CONFIG, statsd
from sovereign.utils.crypto import decrypt, KEY_AVAILABLE, InvalidToken


cache = SimpleCache()


def memoize(timeout):
    """
    Decorator to cache a function by name/args

    :param timeout: How long to keep the result
    """
    if isinstance(timeout, timedelta):
        timeout = timeout.seconds

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


def envoy_authorization_required(decorated):
    """
    Decorator that checks a functions args for something that resembles
    an envoy discovery request, and attempts to decrypt the authorization that
    it contains.

    Raises an exception if there is no discovery request, or if the
    authorization token fails to decrypt.
    """
    @wraps(decorated)
    def wrapper(*args, **kwargs):
        auth_enabled_ = CONFIG.get('auth_required') or CONFIG.get('auth_enabled')
        if auth_enabled_ and not KEY_AVAILABLE:
            raise RuntimeError('No Fernet key loaded, and auth is enabled.')
        if not kwargs.get('debug') and auth_enabled_:
            for arg in args:
                if _request_contains_valid_auth(arg):
                    statsd.increment('discovery.auth.success')
                    break
            else:
                # No arg could be found with auth
                statsd.increment('discovery.auth.failed')
                raise Unauthorized('No authentication provided')
        return decorated(*args, **kwargs)
    return wrapper


def _request_contains_valid_auth(wrapped_fn_argument):
    try:
        metadata = wrapped_fn_argument['node']['metadata']
        auth = metadata.pop('auth')  # Consume the auth, it's not needed past here
        decrypt(auth)
        return True
    except (KeyError, AttributeError):
        pass
    except InvalidToken:
        raise Unauthorized('The authentication provided was invalid')
    except Exception:
        raise BadRequest('The request was malformed')


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
