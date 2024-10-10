import pytest
from starlette.testclient import TestClient


def test_ui_routes_are_displayed(testclient: TestClient):
    response = testclient.get("/ui/resources/routes/rds")
    assert response.status_code == 200
    assert response.json() == {
        "version_info": "3093711546",
        "resources": [
            {
                "name": "rds",
                "virtual_hosts": [
                    {
                        "name": "google-proxy_virtualhost",
                        "domains": ["google.local"],
                        "routes": [
                            {
                                "match": {"path": "/say_hello"},
                                "direct_response": {
                                    "body": {
                                        "inline_string": '{"message": "Hello!", "host_provided": "controlplane"}'
                                    },
                                    "status": 200,
                                },
                                "response_headers_to_add": [
                                    {
                                        "header": {
                                            "key": "Content-Type",
                                            "value": "application/json",
                                        }
                                    }
                                ],
                            },
                            {
                                "match": {"prefix": "/"},
                                "route": {"cluster": "google-proxy_cluster"},
                            },
                        ],
                    },
                    {
                        "name": "httpbin-proxy_virtualhost",
                        "domains": ["example.local"],
                        "routes": [
                            {
                                "match": {"path": "/say_hello"},
                                "direct_response": {
                                    "body": {
                                        "inline_string": '{"message": "Hello!", "host_provided": "controlplane"}'
                                    },
                                    "status": 200,
                                },
                                "response_headers_to_add": [
                                    {
                                        "header": {
                                            "key": "Content-Type",
                                            "value": "application/json",
                                        }
                                    }
                                ],
                            },
                            {
                                "match": {"prefix": "/"},
                                "route": {"cluster": "httpbin-proxy_cluster"},
                            },
                        ],
                    },
                ],
                "@type": "type.googleapis.com/envoy.api.v2.RouteConfiguration",
            }
        ],
    }

def test_ui_routes_are_displayed_in_html(testclient: TestClient):
    response = testclient.get("/ui/resources/routes")
    assert response.status_code == 200
    assert "rds" in response.text
    assert "httpbin-proxy_virtualhost" in response.text
    assert "google-proxy_virtualhost" in response.text

def test_ui_t1_virtualhosts_are_displayed_in_html(testclient: TestClient):
    response = testclient.get("/ui/resources/routes", headers={"Cookie": "service_cluster=T1"})
    assert response.status_code == 200
    assert "rds" in response.text
    assert "httpbin-proxy_virtualhost" in response.text
    assert "google-proxy_virtualhost" not in response.text

def test_ui_x1_virtualhosts_are_displayed_in_html(testclient: TestClient):
    response = testclient.get("/ui/resources/routes", headers={"Cookie": "service_cluster=X1"})
    assert response.status_code == 200
    assert "rds" in response.text
    assert "httpbin-proxy_virtualhost" not in response.text
    assert "google-proxy_virtualhost" in response.text
