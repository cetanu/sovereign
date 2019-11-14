from starlette.testclient import TestClient


class TestEncryptionWorkflow:
    def test_generating_a_key(self, testclient: TestClient):
        response = testclient.get('/crypto/generate_key')
        assert response.status_code == 200
        assert len(response.json()['result']) == 44

    def test_using_the_key_to_encrypt_data(self, testclient: TestClient, random_sovereign_key):
        response = testclient.post('/crypto/encrypt', json={'data': 'hello', 'key': random_sovereign_key})
        encrypted_data = response.json()['result']
        assert len(encrypted_data)

    def test_using_the_key_to_decrypt_data(self, testclient: TestClient, random_sovereign_key):
        response = testclient.post('/crypto/encrypt', json={'data': 'hello', 'key': random_sovereign_key})
        encrypted_data = response.json()['result']
        response = testclient.post('/crypto/decrypt', json={'data': encrypted_data, 'key': random_sovereign_key})
        decrypted_data = response.json()['result']
        assert decrypted_data == 'hello'


class TestEncryptingWithServerKey:
    def test_encrypting_data(self, testclient: TestClient):
        response = testclient.post('/crypto/encrypt', json={'data': 'helloworld'})
        assert response.status_code == 200

    def test_data_is_decryptable(self, testclient: TestClient):
        response = testclient.post('/crypto/encrypt', json={'data': 'helloworld'})
        encrypted_data = response.json()['result']
        response = testclient.post('/crypto/decryptable', json={'data': encrypted_data})
        assert response.status_code == 200, response.json()

    def test_decrypting_without_a_key_is_rejected(self, testclient: TestClient):
        response = testclient.post('/crypto/encrypt', json={'data': 'helloworld'})
        encrypted_data = response.json()['result']
        response = testclient.post('/crypto/decrypt', json={'data': encrypted_data})
        assert response.status_code == 422, response.json()


def test_decrypting_garbage_returns_an_error(testclient: TestClient):
    response = testclient.post('/crypto/decryptable', json={'data': 'foobar'})
    assert response.status_code == 400
    assert response.json() == {'detail': 'Decryption failed'}


def test_decrypting_with_an_invalid_key_returns_an_error(testclient: TestClient):
    response = testclient.post('/crypto/decrypt', json={'data': 'hello', 'key': 'abc'})
    assert response.status_code == 422
    assert response.json() == {
        'detail': [{'loc': ['body', 'request', 'key'],
                    'msg': 'ensure this value has at least 44 characters',
                    'type': 'value_error.any_str.min_length',
                    'ctx': {'limit_value': 44}}]
    }
