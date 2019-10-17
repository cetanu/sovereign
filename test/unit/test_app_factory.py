import pytest
from starlette.testclient import TestClient


def test_docs_redirect(testclient: TestClient):
    response = testclient.get('/', allow_redirects=False)
    assert response.status_code == 307
    assert response.headers['Location'] == '/docs'


def test_stylesheet_exists(testclient: TestClient):
    response = testclient.get('/static/style.css')
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'text/css; charset=utf-8'



# To be moved somewhere more appropriate
def test_encrypting_with_bad_key_fails(testclient: TestClient):
    with pytest.raises(ValueError):
        testclient.post('/crypto/decrypt', json={'data': 'helloworld', 'key': 'f' * 44})

