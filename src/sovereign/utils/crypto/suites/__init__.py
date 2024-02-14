from enum import StrEnum

from sovereign.utils.crypto.suites.aes_gcm_cipher import AESGCMCipher
from sovereign.utils.crypto.suites.base_cipher import CipherSuite
from sovereign.utils.crypto.suites.disabled_cipher import DisabledCipher
from sovereign.utils.crypto.suites.fernet_cipher import FernetCipher


class EncryptionType(StrEnum):
    FERNET = "fernet"
    AESGCM = "aesgcm"
    DISABLED = "disabled"


__all__ = [
    "AESGCMCipher",
    "CipherSuite",
    "DisabledCipher",
    "FernetCipher",
    "EncryptionType",
]
