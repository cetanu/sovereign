import pytest
from fastapi.exceptions import HTTPException

from sovereign.schemas import EncryptionConfig
from sovereign.utils.auth import authenticate, validate_authentication_string
from sovereign.utils.crypto.crypto import CipherContainer
from sovereign.utils.crypto.suites import EncryptionType


def test_validate_passes_on_auth_fixture(auth_string):
    assert validate_authentication_string(auth_string)


@pytest.mark.parametrize(
    "bad_input",
    [
        98123197824,
        1.0,
    ],
)
def test_validate_fails_on_badly_typed_input(bad_input):
    with pytest.raises(HTTPException) as exc_info:
        validate_authentication_string(bad_input)
        assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    "encryption_type",
    [
        EncryptionType.FERNET,
        EncryptionType.AESGCM,
    ],
)
def test_validate_fails_for_bad_password(encryption_type, mock_logger):
    with pytest.raises(HTTPException) as exc_info:
        cipher_container = CipherContainer.from_encryption_configs(
            encryption_configs=[EncryptionConfig("testkey", encryption_type)],
            logger=mock_logger,
        )
        encrypted_data = cipher_container.encrypt("not valid")["encrypted_data"]
        validate_authentication_string(encrypted_data)
        assert exc_info.value.status_code == 400


def test_authenticate_works_with_mock_request(discovery_request, auth_string):
    discovery_request.node.metadata["auth"] = auth_string
    authenticate(discovery_request)


def test_authenticate_rejects_a_request_with_missing_auth(discovery_request):
    with pytest.raises(HTTPException) as exc_info:
        authenticate(discovery_request)
        assert exc_info.value.status_code == 401


@pytest.mark.parametrize(
    "encryption_type",
    [
        EncryptionType.FERNET,
        EncryptionType.AESGCM,
    ],
)
def test_authenticate_rejects_auth_which_does_not_match_configured_passwords(
    encryption_type,
    mock_logger,
    discovery_request,
):
    cipher_container = CipherContainer.from_encryption_configs(
        encryption_configs=[EncryptionConfig("f" * 32, encryption_type)],
        logger=mock_logger,
    )

    with pytest.raises(HTTPException) as exc_info:
        discovery_request.node.metadata["auth"] = cipher_container.encrypt("not valid")
        authenticate(discovery_request)
        assert exc_info.value.status_code == 401


@pytest.mark.parametrize(
    "bad_input",
    [
        98123197824,
        1.0,
        object,
        dict(),
    ],
)
def test_authenticate_rejects_badly_typed_input(bad_input):
    with pytest.raises(HTTPException) as exc_info:
        authenticate(bad_input)
        assert exc_info.value.status_code == 400
