from typing import Optional, Union
from cryptography.fernet import Fernet, InvalidToken
from fastapi.exceptions import HTTPException
from sovereign import config, logs

ENCRYPTION_KEY = config.authentication.encryption_key.get_secret_value().encode()


class DisabledSuite:
    @staticmethod
    def encrypt(_: bytes) -> bytes:
        return b"Unavailable (No Secret Key)"

    @staticmethod
    def decrypt(*_: bytes) -> str:
        return "Unavailable (No Secret Key)"


disabled_suite = DisabledSuite()

try:
    _cipher_suite: Union[Fernet, DisabledSuite] = Fernet(ENCRYPTION_KEY)
    KEY_AVAILABLE = True
except TypeError:
    KEY_AVAILABLE = False
    _cipher_suite = disabled_suite
except ValueError as e:
    if ENCRYPTION_KEY not in (b"", ""):
        logs.application_log(
            event=f"Fernet key was provided, but appears to be invalid: {repr(e)}"
        )
        _cipher_suite = disabled_suite
    KEY_AVAILABLE = False


def encrypt(data: str, key: Optional[str] = None) -> str:
    _local_cipher_suite = _cipher_suite
    if isinstance(key, str):
        _local_cipher_suite = Fernet(key.encode())
    try:
        encrypted: bytes = _local_cipher_suite.encrypt(data.encode())
    except (InvalidToken, AttributeError):
        raise HTTPException(status_code=400, detail="Encryption failed")
    return encrypted.decode()


def decrypt(data: str, key: Optional[str] = None) -> str:
    _local_cipher_suite = _cipher_suite
    if key is not None:
        _local_cipher_suite = Fernet(key.encode())
    try:
        decrypted = _local_cipher_suite.decrypt(data.encode())
    except (InvalidToken, AttributeError):
        raise HTTPException(status_code=400, detail="Decryption failed")
    if isinstance(decrypted, bytes):
        return decrypted.decode()
    else:
        return decrypted


def generate_key() -> str:
    secret: bytes = Fernet.generate_key()
    return secret.decode()
