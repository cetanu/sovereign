import pytest
from starlette.testclient import TestClient

from sovereign import stats
from sovereign.schemas import DiscoveryRequest
from sovereign.utils.mock import mock_discovery_request
from sovereign.views.discovery import perform_discovery


@pytest.mark.asyncio
async def test_mock_discovery_request_should_give_back_all_resources():
    req = mock_discovery_request(
        service_cluster="T1", version="1.30.0", region="ap-southeast-2"
    )
    response = await perform_discovery(
        req=req,
        api_version="V3",
        resource_type="routes",
        skip_auth=True,
    )
    resources = response.deserialize_resources()
    assert resources != []
    assert resources[0]["name"] == "rds"
    assert resources[0]["virtual_hosts"][0]["name"] == "httpbin-proxy_virtualhost"


def test_a_discovery_request_with_bad_auth_fails_with_a_description(
    testclient: TestClient, discovery_request: DiscoveryRequest
):
    stats.emitted.clear()
    assert not stats.emitted.get("discovery.auth.failed")
    req = discovery_request
    req.node.metadata["auth"] = "woop de doo"
    response = testclient.post("/v3/discovery:clusters", json=req.model_dump())
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "The authentication provided was malformed [Reason: Decryption failed]"
    )
    assert stats.emitted.get("discovery.auth.failed") == 1, stats.emitted


class TestRouteDiscovery:
    def test_routes_endpoint_returns_all_route_configs(
        self, testclient: TestClient, discovery_request_with_auth: DiscoveryRequest
    ):
        stats.emitted.clear()
        assert not stats.emitted.get("discovery.rq_total")
        assert not stats.emitted.get("discovery.auth.success")
        req = discovery_request_with_auth
        response = testclient.post("/v3/discovery:routes", json=req.model_dump())
        data = response.json()
        assert response.status_code == 200, response.content
        assert len(data["resources"]) == 1
        assert stats.emitted.get("discovery.rq_ms") == 1, stats.emitted
        assert stats.emitted.get("discovery.rq_total") == 1, stats.emitted
        assert stats.emitted.get("discovery.auth.success") == 1, stats.emitted
        # assert stats.emitted.get("discovery.routes.cache_miss") == 1, stats.emitted
        for route_config in data["resources"]:
            assert (
                route_config["@type"]
                == "type.googleapis.com/envoy.config.route.v3.RouteConfiguration"
            )
            assert route_config["name"] == "rds"
            assert len(route_config["virtual_hosts"]) == 1
            for virtual_host in route_config["virtual_hosts"]:
                assert virtual_host["name"] == "httpbin-proxy_virtualhost"

    @pytest.mark.parametrize("route_config_name", ["rds"])
    def test_routes_endpoint_returns_a_specific_route_config_when_requested(
        self,
        testclient: TestClient,
        discovery_request_with_auth: DiscoveryRequest,
        route_config_name,
    ):
        stats.emitted.clear()
        req = discovery_request_with_auth
        req.resource_names = [route_config_name]
        response = testclient.post("/v3/discovery:routes", json=req.model_dump())
        data = response.json()
        assert response.status_code == 200, response.content
        # assert stats.emitted.get("discovery.routes.cache_miss") == 1, stats.emitted
        assert len(data["resources"]) == 1
        for route_config in data["resources"]:
            assert (
                route_config["@type"]
                == "type.googleapis.com/envoy.config.route.v3.RouteConfiguration"
            )
            assert route_config["name"] == route_config_name

    def test_xds_discovery_with_error_detail(
        self,
        testclient: TestClient,
        discovery_request_with_error_detail: DiscoveryRequest,
    ):
        req = discovery_request_with_error_detail
        response = testclient.post("/v3/discovery:routes", json=req.model_dump())
        data = response.json()
        assert response.status_code == 200, response.content
        assert len(data["resources"]) == 1


class TestListenerDiscovery:
    def test_listeners_endpoint_returns_all_listeners(
        self, testclient: TestClient, discovery_request_with_auth: DiscoveryRequest
    ):
        stats.emitted.clear()
        req = discovery_request_with_auth
        response = testclient.post("/v3/discovery:listeners", json=req.model_dump())
        data = response.json()
        assert response.status_code == 200, response.content
        # assert stats.emitted.get("discovery.listeners.cache_miss") == 1, stats.emitted
        assert len(data["resources"]) == 2

    @pytest.mark.parametrize("listener_name", ("port80", "https_listener"))
    def test_listeners_endpoint_returns_a_specific_listener_when_requested(
        self,
        testclient: TestClient,
        discovery_request_with_auth: DiscoveryRequest,
        listener_name,
    ):
        stats.emitted.clear()
        req = discovery_request_with_auth
        req.resource_names = [listener_name]
        response = testclient.post("/v3/discovery:listeners", json=req.model_dump())
        response.raise_for_status()
        data = response.json()
        assert response.status_code == 200, response.content
        # assert stats.emitted.get("discovery.listeners.cache_miss") == 1, stats.emitted
        assert len(data["resources"]) == 1
        for listener in data["resources"]:
            assert (
                listener["@type"]
                == "type.googleapis.com/envoy.config.listener.v3.Listener"
            )
            assert listener["name"] == listener_name


class TestClustersDiscovery:
    def test_clusters_endpoint_returns_the_configured_instance_as_an_envoy_cluster(
        self,
        testclient: TestClient,
        discovery_request_with_auth: DiscoveryRequest,
        sources,
    ):
        stats.emitted.clear()
        req = discovery_request_with_auth
        # Remove this since it's not relevant for clusters, but also because it tests all paths through discovery
        req.hide_private_keys = False
        response = testclient.post("/v3/discovery:clusters", json=req.model_dump())
        data = response.json()
        assert response.status_code == 200
        # assert stats.emitted.get("discovery.clusters.cache_miss") == 1, stats.emitted
        assert data["resources"] == [
            {
                "@type": "type.googleapis.com/envoy.config.cluster.v3.Cluster",
                "connect_timeout": "5.000s",
                "load_assignment": {
                    "cluster_name": "httpbin-proxy_cluster",
                    "endpoints": [
                        {
                            "lb_endpoints": [
                                {
                                    "endpoint": {
                                        "address": {
                                            "socket_address": {
                                                "address": "httpbin.org",
                                                "port_value": 443,
                                            }
                                        }
                                    }
                                }
                            ],
                            "locality": {"zone": "unknown"},
                            "priority": 10,
                        }
                    ],
                },
                "name": "httpbin-proxy",
                "transport_socket": {
                    "name": "envoy.transport_sockets.tls",
                    "typed_config": {
                        "@type": "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext"
                    },
                },
                "type": "STRICT_DNS",
            }
        ]

    def test_clusters_endpoint_returns_the_configured_instance_for_different_template(
        self,
        testclient: TestClient,
        discovery_request_with_auth: DiscoveryRequest,
        sources,
    ):
        stats.emitted.clear()
        req = discovery_request_with_auth
        # Remove this since it's not relevant for clusters, but also because it tests all paths through discovery
        req.hide_private_keys = False
        req.node.build_version = (
            "15baf56003f33a07e0ab44f82f75a660040db438/1.25.0/Clean/RELEASE"
        )
        response = testclient.post("/v3/discovery:clusters", json=req.model_dump())
        data = response.json()
        assert response.status_code == 200
        assert data["resources"] == [
            {
                "@type": "type.googleapis.com/envoy.config.cluster.v3.Cluster",
                "connect_timeout": "5.000s",
                "load_assignment": {
                    "cluster_name": "httpbin-proxy_cluster",
                    "endpoints": [
                        {
                            "lb_endpoints": [
                                {
                                    "endpoint": {
                                        "address": {
                                            "socket_address": {
                                                "address": "httpbin.org",
                                                "port_value": 443,
                                            }
                                        }
                                    }
                                }
                            ],
                            "locality": {"zone": "unknown"},
                            "priority": 10,
                        }
                    ],
                },
                "name": "httpbin-proxy",
                "transport_socket": {
                    "name": "envoy.transport_sockets.tls",
                    "typed_config": {
                        "@type": "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext"
                    },
                },
                "type": "STRICT_DNS",
            }
        ]

    def test_clusters_with_uptodate_config_returns_304(
        self,
        testclient: TestClient,
        discovery_request_with_auth: DiscoveryRequest,
        sources,
    ):
        stats.emitted.clear()
        req = discovery_request_with_auth
        response = testclient.post("/v3/discovery:clusters", json=req.model_dump())
        assert response.status_code == 200, response.content
        assert response.text != ""
        data = response.json()
        # assert stats.emitted.get("discovery.clusters.cache_hit") == 1, stats.emitted

        req = discovery_request_with_auth
        req.version_info = data["version_info"]
        assert req.version_info != ""
        assert isinstance(req.version_info, str)
        response = testclient.post("/v3/discovery:clusters", json=req.model_dump())
        assert str(req.version_info) not in response.text
        assert response.status_code == 304, response.content
        assert response.text == ""
        # assert stats.emitted.get("discovery.clusters.cache_hit") == 2, stats.emitted

    def test_clusters_with_up_to_date_config_but_different_id_still_returns_304(
        self, testclient: TestClient, discovery_request_with_auth: DiscoveryRequest
    ):
        stats.emitted.clear()
        req = discovery_request_with_auth
        response = testclient.post("/v3/discovery:clusters", json=req.model_dump())
        data = response.json()

        req = discovery_request_with_auth
        req.node.id = "HelloWorld!:)"
        req.node.metadata["stuff"] = "1"
        req.version_info = data["version_info"]
        response = testclient.post("/v3/discovery:clusters", json=req.model_dump())
        assert response.status_code == 304, response.content
        # assert stats.emitted.get("discovery.clusters.cache_hit") == 2, stats.emitted


class TestSecretDiscovery:
    def test_secrets_endpoint_provides_certificate(
        self, testclient: TestClient, discovery_request_with_auth: DiscoveryRequest
    ):
        stats.emitted.clear()
        req = discovery_request_with_auth
        req.resource_names = ["certificates_1"]
        response = testclient.post("/v3/discovery:secrets", json=req.model_dump())
        data = response.json()
        assert response.status_code == 200, response.content
        # assert stats.emitted.get("discovery.secrets.cache_miss") == 1, stats.emitted
        for resource in data["resources"]:
            assert (
                resource["@type"]
                == "type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.Secret"
            )
            assert resource["name"] == "certificates_1"
            assert "tls_certificate" in resource
            assert (
                resource["tls_certificate"]["private_key"]["inline_string"]
                == "Unavailable (No Secret Key)"
            )

    def test_secrets_request_with_up_to_date_config_version_returns_304(
        self, testclient: TestClient, discovery_request_with_auth: DiscoveryRequest
    ):
        stats.emitted.clear()
        req = discovery_request_with_auth
        req.resource_names = ["certificates_1"]
        response = testclient.post("/v3/discovery:secrets", json=req.model_dump())
        data = response.json()

        req = discovery_request_with_auth
        req.resource_names = ["certificates_1"]
        req.version_info = data["version_info"]
        response = testclient.post("/v3/discovery:secrets", json=req.model_dump())
        assert response.status_code == 304, response.content
        # assert stats.emitted.get("discovery.secrets.cache_hit") == 2, stats.emitted

    def test_secrets_returns_404_for_a_bad_cert_name(
        self, testclient: TestClient, discovery_request_with_auth: DiscoveryRequest
    ):
        req = discovery_request_with_auth
        req.resource_names = ["doesNotExist"]
        response = testclient.post("/v3/discovery:secrets", json=req.model_dump())
        assert response.status_code == 404, response.content
