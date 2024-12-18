from sovereign import __version__
from starlette.testclient import TestClient


def test_openapi_json(testclient: TestClient):
    response = testclient.get("/openapi.json")
    assert response.status_code == 200


def test_version_route(testclient: TestClient):
    response = testclient.get("/version")
    assert __version__ in response.content.decode()


def test_healthcheck_route(testclient: TestClient):
    response = testclient.get("/healthcheck")
    assert response.content.decode() == "OK"
    assert response.status_code == 200


def test_deepcheck_route(testclient: TestClient):
    response = testclient.get("/deepcheck")
    assert response.status_code == 200
