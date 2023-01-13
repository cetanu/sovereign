import pytest
from fastapi.exceptions import HTTPException
from sovereign import cipher_suite, logs
from sovereign.utils.crypto import CipherContainer, create_cipher_suite, generate_key


def test_an_encrypted_string_can_be_decrypted_again(random_string):
    encrypted_secret = cipher_suite.encrypt(random_string)
    decrypted_string = cipher_suite.decrypt(encrypted_secret)
    assert decrypted_string == random_string


def test_a_string_encrypted_with_a_custom_key_can_be_decrypted_again(
    random_sovereign_key, random_string
):
    encrypted_secret = cipher_suite.encrypt(random_string, key=random_sovereign_key)
    decrypted_string = cipher_suite.decrypt(encrypted_secret, key=random_sovereign_key)
    assert decrypted_string == random_string


def test_decrypting_with_the_wrong_key_raises_an_exception(
    auth_string, random_sovereign_key
):
    with pytest.raises(HTTPException) as e:
        cipher_suite.decrypt(auth_string, random_sovereign_key)
        assert e.status_code == 400
        assert e.detail == "Decryption failed"


def test_decrypting_value_with_multiple_keys():
    # Create multiple keys
    keys = [generate_key(), generate_key()]

    # Create suite
    suite = CipherContainer(
        [create_cipher_suite(key.encode(), logs) for key in keys]
    )
    # create encrypted value
    encrypted = suite.encrypt("helloworld")

    # value can be decrypted
    assert suite.decrypt(encrypted) == "helloworld"

    # swap keys in-place and re-create suite
    keys.reverse()
    suite = CipherContainer(
        [create_cipher_suite(key.encode(), logs) for key in keys]
    )

    # value can still be decrypted
    assert suite.decrypt(encrypted) == "helloworld"
