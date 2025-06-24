from cryptography.fernet import InvalidToken
from fastapi.exceptions import HTTPException

from sovereign import config, server_cipher_container, stats, application_logger as log
from sovereign.schemas import DiscoveryRequest

AUTH_ENABLED = config.authentication.enabled


@stats.timed("discovery.auth.ms")
def validate_authentication_string(s: str) -> bool:
    try:
        password = server_cipher_container.decrypt(s)
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
    if not server_cipher_container.key_available:
        raise RuntimeError(
            "No encryption key loaded, and auth is enabled. "
            "An encryption key must be provided via SOVEREIGN_ENCRYPTION_KEY. "
        )
    try:
        encrypted_auth = request.node.metadata["auth"]
    except KeyError:
        raise HTTPException(
            status_code=401,
            detail=f"Discovery request from {request.node.id} is missing auth field",
        )
    except Exception as e:
        description = getattr(e, "detail", "unknown")
        raise HTTPException(
            status_code=400,
            detail=f"The authentication provided was malformed [Reason: {description}]",
        )

    try:
        assert isinstance(encrypted_auth, str)
        assert validate_authentication_string(encrypted_auth)
    except (InvalidToken, AssertionError):
        raise HTTPException(
            status_code=401, detail="The authentication provided was invalid"
        )
    except Exception as e:
        alt_desc = repr(e)
        alt_desc = alt_desc.replace(encrypted_auth, "********")
        for password in config.passwords:
            alt_desc = alt_desc.replace(password, "********")
        description = getattr(e, "detail", alt_desc)
        log.exception(f"Failed to auth client: {description}")
        raise HTTPException(
            status_code=400,
            detail=f"The authentication provided was malformed [Reason: {description}]",
        )
