from abc import ABC, abstractmethod
from typing import Any


class CipherSuite(ABC):
    @abstractmethod
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        ...

    @abstractmethod
    def encrypt(self, data: str) -> str:
        ...

    @abstractmethod
    def decrypt(self, data: str) -> str:
        ...

    @property
    @abstractmethod
    def key_available(self) -> bool:
        ...

    @classmethod
    @abstractmethod
    def generate_key(cls) -> bytes:
        ...
