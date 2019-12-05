import json
import pytest
from starlette.testclient import TestClient
from starlette.exceptions import HTTPException
from sovereign.app import generic_error_response


def test_index_redirects_to_interface(testclient: TestClient):
    response = testclient.get('/', allow_redirects=False)
    assert response.status_code == 307
    assert response.headers['Location'] == '/ui'


def test_css_stylesheet_exists(testclient: TestClient):
    response = testclient.get('/static/style.css')
    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'text/css; charset=utf-8'


def test_error_handler_returns_json_response():
    response = generic_error_response(ValueError('Hello'))
    assert response.status_code == 500
    jsondata = json.loads(response.body.decode())
    assert jsondata == {"error": "ValueError", "detail": "-", "request_id": None, "traceback": ["NoneType: None", ""]}


def test_error_handler_responds_with_json_for_starlette_exceptions():
    response = generic_error_response(HTTPException(429, 'Too Many Requests!'))
    assert response.status_code == 429
    jsondata = json.loads(response.body.decode())
    assert jsondata == {"error": "HTTPException", "detail": "Too Many Requests!", "request_id": None, "traceback": ["NoneType: None", ""]}


# To be moved somewhere more appropriate
def test_supplying_a_bad_key_for_encryption_fails(testclient: TestClient):
    with pytest.raises(ValueError):
        testclient.post('/crypto/decrypt', json={'data': 'helloworld', 'key': 'f' * 44})

