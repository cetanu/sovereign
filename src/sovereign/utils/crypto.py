from collections import namedtuple
from cryptography.fernet import Fernet, InvalidToken
from sovereign import config


try:
    _cipher_suite = Fernet(config.encryption_key)
    KEY_AVAILABLE = True
except TypeError:
    KEY_AVAILABLE = False
    _cipher_suite = namedtuple('DisabledSuite', ['encrypt', 'decrypt'])
    _cipher_suite.encrypt = lambda x: b'Unavailable (No Secret Key)'
    _cipher_suite.decrypt = lambda x: b'Unavailable (No Secret Key)'


def encrypt(data: str, key=None) -> str:
    _local_cipher_suite = _cipher_suite
    if key is not None:
        _local_cipher_suite = Fernet(key)
    try:
        encrypted: bytes = _local_cipher_suite.encrypt(data.encode())
    except InvalidToken:
        raise InvalidToken('Encryption failed')
    except AttributeError:
        raise AttributeError('Encryption failed')
    return encrypted.decode()


def decrypt(data: str, key=None) -> str:
    _local_cipher_suite = _cipher_suite
    if key is not None:
        _local_cipher_suite = Fernet(key)
    try:
        decrypted: bytes = _local_cipher_suite.decrypt(data.encode())
    except InvalidToken:
        raise InvalidToken('Decryption failed')
    except AttributeError:
        raise AttributeError('Decryption failed')
    return decrypted.decode()


def generate_key() -> str:
    secret: bytes = Fernet.generate_key()
    return secret.decode()
