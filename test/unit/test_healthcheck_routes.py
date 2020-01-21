from sovereign import __versionstr__
from starlette.testclient import TestClient


def test_version_route(testclient: TestClient):
    response = testclient.get('/version')
    assert __versionstr__ in response.content.decode()


def test_healthcheck_route(testclient: TestClient):
    response = testclient.get('/healthcheck')
    assert response.content.decode() == 'OK'


def test_deepcheck_route(testclient: TestClient):
    valid_responses = [
        'Rendered listeners OK',
        'Rendered clusters OK',
        'Rendered routes OK',
        'Rendered scoped-routes OK',
        'Rendered endpoints OK',
        'Rendered secrets OK',
    ]
    for _ in range(100):
        response = testclient.get('/deepcheck')
        assert response.content.decode() in valid_responses
