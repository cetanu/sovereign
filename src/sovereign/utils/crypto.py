from functools import partial
from collections import namedtuple
from typing import Optional, List
from cryptography.fernet import Fernet, InvalidToken
from fastapi.exceptions import HTTPException
from structlog.stdlib import BoundLogger

CipherSuite = namedtuple("CipherSuite", "encrypt decrypt key_available")


class CipherContainer:
    """
    Object which intercepts encrypt/decryptions
    Tries to decrypt data using the ciphers provided in order
    Encrypts with the first suite available.
    """

    def __init__(self, suites: List[CipherSuite]) -> None:
        self.suites = suites

    def encrypt(self, data: str, key: Optional[str] = None) -> str:
        if key is not None:
            return encrypt(Fernet(key.encode()), data)
        return self.suites[0].encrypt(data)  # type: ignore

    def decrypt(self, data: str, key: Optional[str] = None) -> str:
        if key is not None:
            return decrypt(Fernet(key.encode()), data)
        success = False
        decrypted = None
        error = ValueError("Unable to decrypt value, unknown error")
        for suite in self.suites:
            try:
                decrypted = suite.decrypt(data)
                success = True
                break
            except (InvalidToken, AttributeError, HTTPException) as e:
                error = e  # type: ignore
                continue
        if not success:
            raise error
        else:
            return decrypted  # type: ignore

    @property
    def key_available(self) -> bool:
        return self.suites[0].key_available  # type: ignore


class DisabledSuite:
    @staticmethod
    def encrypt(_: bytes) -> bytes:
        return b"Unavailable (No Secret Key)"

    @staticmethod
    def decrypt(*_: bytes) -> str:
        return "Unavailable (No Secret Key)"


def create_cipher_suite(key: bytes, logger: BoundLogger) -> CipherSuite:
    try:
        fernet = Fernet(key)
        return CipherSuite(partial(encrypt, fernet), partial(decrypt, fernet), True)
    except TypeError:
        pass
    except ValueError as e:
        if key not in (b"", ""):
            logger.error(
                f"Fernet key was provided, but appears to be invalid: {repr(e)}"
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
