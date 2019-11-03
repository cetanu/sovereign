import pytest
from fastapi.exceptions import HTTPException
from sovereign.utils.crypto import encrypt, decrypt


def test_an_encrypted_string_can_be_decrypted_again(random_string):
    encrypted_secret = encrypt(random_string)
    decrypted_string = decrypt(encrypted_secret)
    assert decrypted_string == random_string


def test_a_string_encrypted_with_a_custom_key_can_be_decrypted_again(random_sovereign_key, random_string):
    encrypted_secret = encrypt(random_string, key=random_sovereign_key)
    decrypted_string = decrypt(encrypted_secret, key=random_sovereign_key)
    assert decrypted_string == random_string


def test_decrypting_with_the_wrong_key_raises_an_exception(auth_string, random_sovereign_key):
    with pytest.raises(HTTPException) as e:
        decrypt(auth_string, random_sovereign_key)
        assert e.status_code == 400
        assert e.detail == 'Decryption failed'
