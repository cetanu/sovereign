import base64
import os
from unittest.mock import MagicMock

import pytest
from fastapi.exceptions import HTTPException

from sovereign.configuration import EncryptionConfig
from sovereign.utils.crypto.crypto import CipherContainer
from sovereign.utils.crypto.suites import EncryptionType


@pytest.mark.parametrize(
    "encryption_type",
    [
        EncryptionType.FERNET,
        EncryptionType.AESGCM,
    ],
)
def test_a_string_encrypted_with_a_custom_key_can_be_decrypted_again(
    encryption_type, random_string, random_sovereign_key_func
):
    cipher_container = CipherContainer.from_encryption_configs(
        encryption_configs=[
            EncryptionConfig(random_sovereign_key_func(), encryption_type)
        ],
        logger=MagicMock(),
    )
    encrypt_output = cipher_container.encrypt(random_string)
    encrypted_secret = encrypt_output["encrypted_data"]

    decrypted_string = cipher_container.decrypt(encrypted_secret)
    assert decrypted_string == random_string


@pytest.mark.parametrize(
    "encryption_type",
    [
        EncryptionType.FERNET,
        EncryptionType.AESGCM,
    ],
)
def test_decrypting_with_the_wrong_key_raises_an_exception(
    encryption_type, auth_string, random_sovereign_key_func
):
    cipher_container = CipherContainer.from_encryption_configs(
        encryption_configs=[
            EncryptionConfig(random_sovereign_key_func(), encryption_type)
        ],
        logger=MagicMock(),
    )

    with pytest.raises(HTTPException) as e:
        cipher_container.decrypt(auth_string)
        assert e.value.status_code == 400
        assert e.value.detail == "Decryption failed"


@pytest.mark.parametrize(
    "encryption_type",
    [
        EncryptionType.FERNET,
        EncryptionType.AESGCM,
    ],
)
def test_decrypting_value_with_multiple_keys(
    encryption_type, mock_logger, random_sovereign_key_func
):
    # Create multiple keys
    encryption_configs = [
        EncryptionConfig(random_sovereign_key_func(), encryption_type),
        EncryptionConfig(random_sovereign_key_func(), encryption_type),
    ]

    # Create suite
    cipher_container = CipherContainer.from_encryption_configs(
        encryption_configs=encryption_configs,
        logger=mock_logger,
    )
    # create encrypted value
    encrypt_output = cipher_container.encrypt("helloworld")
    encrypted_secret = encrypt_output["encrypted_data"]

    # value can be decrypted
    decrypt_output = cipher_container.decrypt(encrypted_secret)
    assert decrypt_output == "helloworld"

    # swap keys in-place and re-create suite
    encryption_configs.reverse()
    cipher_container = CipherContainer.from_encryption_configs(
        encryption_configs=encryption_configs,
        logger=mock_logger,
    )
    # value can still be decrypted
    decrypt_output = cipher_container.decrypt(encrypted_secret)
    assert decrypt_output == "helloworld"


@pytest.mark.parametrize(
    "encryption_type",
    [
        EncryptionType.FERNET,
        EncryptionType.AESGCM,
    ],
)
def test_sucessfully_decrypts_with_encryption_type_return(
    encryption_type, random_string, random_sovereign_key_func
):
    cipher_container = CipherContainer.from_encryption_configs(
        encryption_configs=[
            EncryptionConfig(random_sovereign_key_func(), encryption_type)
        ],
        logger=MagicMock(),
    )
    encrypt_output = cipher_container.encrypt(random_string)
    encrypted_secret = encrypt_output["encrypted_data"]

    decrypt_output = cipher_container.decrypt_with_type(encrypted_secret)
    assert decrypt_output.get("decrypted_data") == random_string
    assert decrypt_output.get("encryption_type") == encryption_type.value
