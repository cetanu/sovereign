import pytest
from starlette.testclient import TestClient


class TestEncryptionWorkflow:
    @pytest.mark.parametrize("encryption_type", ["fernet", "aesgcm"])
    def test_generating_a_key(self, encryption_type, testclient: TestClient):
        response = testclient.get(
            "/crypto/generate_key", params={"encryption_type": encryption_type}
        )
        assert response.status_code == 200
        assert len(response.json()["key"]) == 44

    @pytest.mark.parametrize("encryption_type", ["fernet", "aesgcm"])
    def test_using_the_key_to_encrypt_data(
        self, encryption_type, testclient: TestClient, random_sovereign_key_func
    ):
        response = testclient.post(
            "/crypto/encrypt",
            json={
                "data": "hello",
                "key": random_sovereign_key_func(),
                "encryption_type": encryption_type,
            },
        )
        encrypted_data = response.json()["encrypted_data"]
        assert len(encrypted_data)

    @pytest.mark.parametrize("encryption_type", ["fernet", "aesgcm"])
    def test_using_the_key_to_decrypt_data(
        self, encryption_type, testclient: TestClient, random_sovereign_key_func
    ):
        random_sovereign_key = random_sovereign_key_func()
        response = testclient.post(
            "/crypto/encrypt",
            json={
                "data": "hello",
                "key": random_sovereign_key,
                "encryption_type": encryption_type,
            },
        )
        encrypted_data = response.json()["encrypted_data"]
        response = testclient.post(
            "/crypto/decrypt",
            json={
                "data": encrypted_data,
                "key": random_sovereign_key,
                "encryption_type": encryption_type,
            },
        )
        decrypted_data = response.json()["decrypted_data"]
        assert decrypted_data == "hello"


class TestEncryptingWithServerKey:
    def test_encrypting_data(self, testclient: TestClient):
        response = testclient.post("/crypto/encrypt", json={"data": "helloworld"})
        assert response.status_code == 200

    def test_data_is_decryptable(self, testclient: TestClient):
        response = testclient.post("/crypto/encrypt", json={"data": "helloworld"})
        encrypted_data = response.json()["encrypted_data"]
        response = testclient.post("/crypto/decryptable", json={"data": encrypted_data})
        assert response.status_code == 200, response.json()

    def test_decrypting_without_a_key_is_rejected(self, testclient: TestClient):
        response = testclient.post("/crypto/encrypt", json={"data": "helloworld"})
        encrypted_data = response.json()["encrypted_data"]
        response = testclient.post("/crypto/decrypt", json={"data": encrypted_data})
        assert response.status_code == 422, response.json()


class TestEncryptingWithServerKeyWithEncryptionType:
    @pytest.mark.parametrize("encryption_type", ["fernet", "aesgcm"])
    def test_encrypting_data(self, encryption_type, testclient: TestClient):
        response = testclient.post(
            "/crypto/encrypt",
            json={"data": "helloworld", "encryption_type": encryption_type},
        )
        assert response.status_code == 200

    @pytest.mark.parametrize("encryption_type", ["fernet", "aesgcm"])
    def test_data_is_decryptable(self, encryption_type, testclient: TestClient):
        response = testclient.post(
            "/crypto/encrypt",
            json={"data": "helloworld", "encryption_type": encryption_type},
        )
        encrypted_data = response.json()["encrypted_data"]
        response = testclient.post("/crypto/decryptable", json={"data": encrypted_data})
        assert response.status_code == 200, response.json()

    @pytest.mark.parametrize("encryption_type", ["fernet", "aesgcm"])
    def test_decrypting_without_a_key_is_rejected(
        self, encryption_type, testclient: TestClient
    ):
        response = testclient.post(
            "/crypto/encrypt",
            json={"data": "helloworld", "encryption_type": encryption_type},
        )
        encrypted_data = response.json()["encrypted_data"]
        response = testclient.post("/crypto/decrypt", json={"data": encrypted_data})
        assert response.status_code == 422, response.json()


def test_decrypting_garbage_returns_an_error(testclient: TestClient):
    response = testclient.post("/crypto/decryptable", json={"data": "foobar"})
    assert response.status_code == 400
    assert response.json() == {"detail": "Decryption failed"}


def test_decrypting_with_an_invalid_key_returns_an_error(testclient: TestClient):
    response = testclient.post("/crypto/decrypt", json={"data": "hello", "key": "abc"})
    assert response.status_code == 422
    assert response.json() == {
        "detail": [
            {
                "input": "abc",
                "loc": ["body", "key"],
                "msg": "String should have at least 44 characters",
                "type": "string_too_short",
                "ctx": {"min_length": 44}
            }
        ]
    }
