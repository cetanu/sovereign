from typing import Any

from .base_cipher import CipherSuite


class DisabledCipher(CipherSuite):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def __str__(self) -> str:
        return "disabled"

    def encrypt(self, _: str) -> str:
        return "Unavailable (No Secret Key)"

    def decrypt(self, _: str) -> str:
        return "Unavailable (No Secret Key)"

    @property
    def key_available(self) -> bool:
        return False

    @classmethod
    def generate_key(cls) -> bytes:
        return b"Unavailable (No key to generate)"
