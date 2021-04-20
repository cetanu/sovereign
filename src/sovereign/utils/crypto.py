from cryptography.fernet import Fernet, InvalidToken
from fastapi.exceptions import HTTPException
from sovereign import config
from sovereign.logs import application_log

ENCRYPTION_KEY = config.authentication.encryption_key.get_secret_value()


class DisabledSuite:
    @staticmethod
    def encrypt(_) -> bytes:
        return b"Unavailable (No Secret Key)"

    @staticmethod
    def decrypt(*_) -> str:
        return "Unavailable (No Secret Key)"


disabled_suite = DisabledSuite()

try:
    _cipher_suite = Fernet(ENCRYPTION_KEY)
    KEY_AVAILABLE = True
except TypeError:
    KEY_AVAILABLE = False
    _cipher_suite = disabled_suite
except ValueError as e:
    if ENCRYPTION_KEY != "":
        application_log(
            event=f"Fernet key was provided, but appears to be invalid: {repr(e)}"
        )
        _cipher_suite = disabled_suite
    KEY_AVAILABLE = False


def encrypt(data: str, key=None) -> str:
    _local_cipher_suite = _cipher_suite
    if key is not None:
        _local_cipher_suite = Fernet(key)
    try:
        encrypted: bytes = _local_cipher_suite.encrypt(data.encode())
    except (InvalidToken, AttributeError):
        raise HTTPException(status_code=400, detail="Encryption failed")
    return encrypted.decode()


def decrypt(data: str, key=None) -> str:
    _local_cipher_suite = _cipher_suite
    if key is not None:
        _local_cipher_suite = Fernet(key)
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
