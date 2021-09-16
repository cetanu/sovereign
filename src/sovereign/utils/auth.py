from fastapi.exceptions import HTTPException
from cryptography.fernet import InvalidToken
from sovereign import config, stats
from sovereign.schemas import DiscoveryRequest
from sovereign.utils.crypto import decrypt, KEY_AVAILABLE

AUTH_ENABLED = config.authentication.enabled


def validate_authentication_string(s: str) -> bool:
    try:
        password = decrypt(s)
    except Exception:
        stats.increment("discovery.auth.failed")
        raise

    if password in config.passwords:
        stats.increment("discovery.auth.success")
        return True
    stats.increment("discovery.auth.failed")
    return False


def authenticate(request: DiscoveryRequest) -> None:
    if not AUTH_ENABLED:
        return
    if not KEY_AVAILABLE:
        raise RuntimeError(
            "No Fernet key loaded, and auth is enabled. "
            "A fernet key must be provided via SOVEREIGN_ENCRYPTION_KEY. "
            "See https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/encryption.html "
            "for more details"
        )
    try:
        encrypted_auth = request.node.metadata["auth"]
        with stats.timed("discovery.auth.ms"):
            assert validate_authentication_string(encrypted_auth)
    except KeyError:
        raise HTTPException(
            status_code=401,
            detail=f"Discovery request from {request.node.id} is missing auth field",
        )
    except (InvalidToken, AssertionError):
        raise HTTPException(
            status_code=401, detail="The authentication provided was invalid"
        )
    except Exception as e:
        description = getattr(e, "detail", "Unknown")
        raise HTTPException(
            status_code=400,
            detail=f"The authentication provided was malformed [Reason: {description}]",
        )
