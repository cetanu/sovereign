from fastapi.exceptions import HTTPException
from cryptography.fernet import InvalidToken
from sovereign.schemas import DiscoveryRequest
from sovereign.configuration import CONFIG, STATS, CIPHER_SUITE

AUTH_ENABLED = CONFIG.authentication.enabled


def validate_authentication_string(s: str) -> bool:
    try:
        password = CIPHER_SUITE.decrypt(s)
    except Exception:
        STATS.increment("discovery.auth.failed")
        raise

    if password in CONFIG.passwords:
        STATS.increment("discovery.auth.success")
        return True
    STATS.increment("discovery.auth.failed")
    return False


def authenticate(request: DiscoveryRequest) -> None:
    if not AUTH_ENABLED:
        return
    if not CIPHER_SUITE.key_available:
        raise RuntimeError(
            "No Fernet key loaded, and auth is enabled. "
            "A fernet key must be provided via SOVEREIGN_ENCRYPTION_KEY. "
            "See https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/encryption.html "
            "for more details"
        )
    try:
        encrypted_auth = request.node.metadata["auth"]
        with STATS.timed("discovery.auth.ms"):
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
