from typing import Literal, Self, Sequence

from cachetools import TTLCache, cached
from fastapi.exceptions import HTTPException
from structlog.stdlib import BoundLogger
from typing_extensions import TypedDict

from sovereign.schemas import EncryptionConfig
from sovereign.utils.crypto.suites import (
    AESGCMCipher,
    CipherSuite,
    DisabledCipher,
    EncryptionType,
    FernetCipher,
)


class EncryptOutput(TypedDict):
    encrypted_data: str
    encryption_type: str


class DecryptOutput(TypedDict):
    decrypted_data: str
    encryption_type: str


class CipherContainer:
    """
    Object which intercepts encrypt/decryptions
    Tries to decrypt data using the ciphers provided in order
    Encrypts with the first suite available.
    """

    def __init__(self, suites: Sequence[CipherSuite], logger: BoundLogger) -> None:
        self.suites: Sequence[CipherSuite] = suites
        self.logger = logger

    def encrypt(self, data: str) -> EncryptOutput:
        try:
            # Use the first cipher suite to encrypt the data
            encrypted_data = self.suites[0].encrypt(data)
            return {
                "encrypted_data": encrypted_data,
                "encryption_type": str(self.suites[0]),
            }
        # pylint: disable=broad-except
        except Exception as e:
            self.logger.exception(str(e))
            # TODO: defer this http error to later, return a normal error here
            raise HTTPException(status_code=400, detail="Encryption failed")

    def decrypt_with_type(self, data: str) -> DecryptOutput:
        return self._decrypt(data)

    def decrypt(self, data: str) -> str:
        return self._decrypt(data)["decrypted_data"]

    @cached(cache=TTLCache(maxsize=128, ttl=600))
    def _decrypt(self, data: str) -> DecryptOutput:
        try:
            for suite in self.suites:
                try:
                    decrypted_data = suite.decrypt(data)
                    return {
                        "decrypted_data": decrypted_data,
                        "encryption_type": str(suite),
                    }
                # pylint: disable=broad-except
                except Exception as e:
                    self.logger.exception(str(e))
                    self.logger.debug(f"Failed to decrypt with suite {suite}")
            else:
                raise ValueError("Could not decrypt with any suite")
        except Exception as e:
            self.logger.exception(str(e))
            # TODO: defer this http error to later, return a normal error here
            raise HTTPException(status_code=400, detail="Decryption failed")

    @property
    def key_available(self) -> bool:
        if not self.suites:
            return False
        return self.suites[0].key_available

    AVAILABLE_CIPHERS: dict[EncryptionType | Literal["default"], type[CipherSuite]] = {
        EncryptionType.DISABLED: DisabledCipher,
        EncryptionType.AESGCM: AESGCMCipher,
        EncryptionType.FERNET: FernetCipher,
        "default": FernetCipher,
    }

    @classmethod
    def get_cipher_suite(cls, encryption_type: EncryptionType) -> type[CipherSuite]:
        SelectedCipher = cls.AVAILABLE_CIPHERS.get(
            encryption_type, cls.AVAILABLE_CIPHERS["default"]
        )
        return SelectedCipher

    @classmethod
    def create_cipher_suite(
        cls,
        encryption_type: EncryptionType,
        key: str,
        logger: BoundLogger,
    ) -> CipherSuite:
        kwargs = {
            "secret_key": key,
        }
        try:
            SelectedCipher = cls.get_cipher_suite(encryption_type)
            return SelectedCipher(**kwargs)
        except TypeError:
            pass
        except ValueError as e:
            if key not in (b"", ""):
                logger.error(
                    f"Encryption key was provided, but appears to be invalid: {repr(e)}"
                )
        return DisabledCipher(**kwargs)

    @classmethod
    def from_encryption_configs(
        cls, encryption_configs: Sequence[EncryptionConfig], logger: BoundLogger
    ) -> Self:
        cipher_suites: list[CipherSuite] = []
        for encryption_config in encryption_configs:
            cipher_suites.append(
                cls.create_cipher_suite(
                    key=encryption_config.encryption_key,
                    encryption_type=encryption_config.encryption_type,
                    logger=logger,
                )
            )
        return cls(suites=cipher_suites, logger=logger)
