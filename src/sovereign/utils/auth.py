from werkzeug.exceptions import Unauthorized, BadRequest
from sovereign import config, statsd, __version__
from sovereign.dataclasses import DiscoveryRequest
from sovereign.utils.crypto import decrypt, KEY_AVAILABLE, InvalidToken


def validate(auth_string):
    try:
        password = decrypt(auth_string)
    except Exception:
        statsd.increment('discovery.auth.failed')
        raise

    if password in config.passwords:
        statsd.increment('discovery.auth.success')
        return True
    statsd.increment('discovery.auth.failed')
    return False


def authenticate(request: DiscoveryRequest):
    if not config.auth_enabled:
        return
    if not KEY_AVAILABLE:
        raise RuntimeError(
            'No Fernet key loaded, and auth is enabled. '
            'A fernet key must be provided via SOVEREIGN_ENCRYPTION_KEY. '
            'See https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/encryption.html '
            'for more details'
        )
    try:
        encrypted_auth = request.node.metadata['auth']
        assert validate(encrypted_auth)
    except KeyError:
        raise KeyError(f'Discovery request from {request.node.id} is missing auth field')
    except (InvalidToken, AssertionError):
        raise Unauthorized('The authentication provided was invalid')
    except Exception:
        raise BadRequest('The request was malformed')
