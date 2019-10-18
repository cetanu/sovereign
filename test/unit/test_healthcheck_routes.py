from sovereign import __versionstr__
from starlette.testclient import TestClient


def test_version_route(testclient: TestClient):
    response = testclient.get('/version')
    assert __versionstr__ in response.content.decode()


def test_healthcheck_route(testclient: TestClient):
    response = testclient.get('/healthcheck')
    assert response.content.decode() == 'OK'


def test_deepcheck_route(testclient: TestClient):
    for _ in range(100):
        response = testclient.get('/deepcheck')
        assert response.content.decode() == 'OK'


def test_request_id_route(testclient: TestClient):
    response = testclient.get('/request_id')
    assert len(response.content) == 36
