import pytest
from quart.exceptions import BadRequest
from sovereign.utils.crypto import encrypt, decrypt


def test_encryption_happy_path(random_string):
    encrypted_secret = encrypt(random_string)
    decrypted_string = decrypt(encrypted_secret)
    assert decrypted_string == random_string


def test_encrypting_with_custom_key(random_sovereign_key, random_string):
    encrypted_secret = encrypt(random_string, key=random_sovereign_key)
    decrypted_string = decrypt(encrypted_secret, key=random_sovereign_key)
    assert decrypted_string == random_string


def test_encrypting_with_wrong_key(auth_string, random_sovereign_key):
    with pytest.raises(BadRequest):
        decrypt(auth_string, random_sovereign_key)
