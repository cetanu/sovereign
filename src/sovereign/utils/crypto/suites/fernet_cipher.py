import base64
import os

from cryptography.fernet import Fernet

from .base_cipher import CipherSuite


class FernetCipher(CipherSuite):
    def __str__(self) -> str:
        return "fernet"

    def __init__(self, secret_key: str):
        self.fernet = Fernet(secret_key)

    def encrypt(self, data: str) -> str:
        return self.fernet.encrypt(data.encode()).decode("utf-8")

    def decrypt(self, data: str) -> str:
        return self.fernet.decrypt(data).decode("utf-8")

    @property
    def key_available(self) -> bool:
        return True

    @classmethod
    def generate_key(cls) -> bytes:
        # Generate 256 bit length key
        return base64.urlsafe_b64encode(os.urandom(32))
