from functools import partial
from collections import namedtuple
from typing import Optional, Any
from cryptography.fernet import Fernet, InvalidToken
from fastapi.exceptions import HTTPException


CipherSuite = namedtuple("CipherSuite", "encrypt decrypt key_available")


class DisabledSuite:
    @staticmethod
    def encrypt(_: bytes) -> bytes:
        return b"Unavailable (No Secret Key)"

    @staticmethod
    def decrypt(*_: bytes) -> str:
        return "Unavailable (No Secret Key)"


def create_cipher_suite(key: bytes, logger: Any) -> CipherSuite:
    try:
        fernet = Fernet(key)
        return CipherSuite(partial(encrypt, fernet), partial(decrypt, fernet), True)
    except TypeError:
        pass
    except ValueError as e:
        if key not in (b"", ""):
            logger.application_log(
                event=f"Fernet key was provided, but appears to be invalid: {repr(e)}"
            )
    return CipherSuite(DisabledSuite.encrypt, DisabledSuite.decrypt, False)


def generate_key() -> str:
    secret: bytes = Fernet.generate_key()
    return secret.decode()


def encrypt(cipher_suite: Fernet, data: str, key: Optional[str] = None) -> str:
    _local_cipher_suite = cipher_suite
    if isinstance(key, str):
        _local_cipher_suite = Fernet(key.encode())
    try:
        encrypted: bytes = _local_cipher_suite.encrypt(data.encode())
    except (InvalidToken, AttributeError):
        # TODO: defer this http error to later, return a normal error here
        raise HTTPException(status_code=400, detail="Encryption failed")
    return encrypted.decode()


def decrypt(cipher_suite: Fernet, data: str, key: Optional[str] = None) -> str:
    _local_cipher_suite = cipher_suite
    if key is not None:
        _local_cipher_suite = Fernet(key.encode())
    try:
        decrypted = _local_cipher_suite.decrypt(data.encode())
    except (InvalidToken, AttributeError):
        # TODO: defer this http error to later, return a normal error here
        raise HTTPException(status_code=400, detail="Decryption failed")
    if isinstance(decrypted, bytes):
        return decrypted.decode()
    else:
        return decrypted
