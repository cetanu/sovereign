import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .base_cipher import CipherSuite


class AESGCMCipher(CipherSuite):
    AUTHENTICATE_DATA = "sovereign".encode()
    NONCE_LEN = 12

    def __str__(self) -> str:
        return "aesgcm"

    def __init__(self, secret_key: str):
        self.secret_key = base64.urlsafe_b64decode(secret_key)

    def encrypt(self, data: str) -> str:
        aesgcm = AESGCM(self.secret_key)
        nonce = os.urandom(self.NONCE_LEN)
        ct = aesgcm.encrypt(nonce, data.encode(), self.AUTHENTICATE_DATA)
        return base64.b64encode(nonce + ct).decode("utf-8")

    def decrypt(self, data: str) -> str:
        decoded_data = base64.b64decode(data)
        nonce, ct = (
            decoded_data[: self.NONCE_LEN],
            decoded_data[self.NONCE_LEN :],
        )
        aesgcm = AESGCM(self.secret_key)
        decrypted_output = aesgcm.decrypt(nonce, ct, self.AUTHENTICATE_DATA)
        return decrypted_output.decode("utf-8")

    @property
    def key_available(self) -> bool:
        return True

    @classmethod
    def generate_key(cls) -> bytes:
        # Generate 256 bit length key
        return base64.urlsafe_b64encode(os.urandom(32))
