import pytest
from sovereign.schemas import DiscoveryRequest
from starlette.testclient import TestClient
from sovereign.statistics import stats


def test_a_discovery_request_with_bad_auth_fails_with_a_description(testclient: TestClient, discovery_request: DiscoveryRequest):
    stats.emitted.clear()
    assert not stats.emitted.get('discovery.auth.failed')
    req = discovery_request
    req.node.metadata['auth'] = 'woop de doo'
    response = testclient.post('/v2/discovery:clusters', json=req.dict())
    assert stats.emitted.get('discovery.auth.failed') == 1, stats.emitted
    assert response.status_code == 400
    assert response.json()['detail'] == 'The authentication provided was malformed [Reason: Decryption failed]'


class TestRouteDiscovery:
    def test_routes_endpoint_returns_all_route_configs(self, testclient: TestClient, discovery_request_with_auth: DiscoveryRequest):
        stats.emitted.clear()
        assert not stats.emitted.get('discovery.rq_total')
        assert not stats.emitted.get('discovery.auth.success')
        req = discovery_request_with_auth
        response = testclient.post('/v2/discovery:routes', json=req.dict())
        assert stats.emitted.get('discovery.rq_ms') == 1, stats.emitted
        assert stats.emitted.get('discovery.rq_total') == 1, stats.emitted
        assert stats.emitted.get('discovery.auth.success') == 1, stats.emitted
        data = response.json()
        assert response.status_code == 200, response.content
        assert len(data['resources']) == 1
        for route_config in data['resources']:
            assert route_config['@type'] == 'type.googleapis.com/envoy.api.v2.RouteConfiguration'
            assert route_config['name'] == 'rds'
            assert len(route_config['virtual_hosts']) == 1
            for virtual_host in route_config['virtual_hosts']:
                assert virtual_host['name'] == 'httpbin-proxy_virtualhost'

    @pytest.mark.parametrize("route_config_name", ['rds'])
    def test_routes_endpoint_returns_a_specific_route_config_when_requested(self, testclient: TestClient,
                                                                            discovery_request_with_auth: DiscoveryRequest,
                                                                            route_config_name):
        req = discovery_request_with_auth
        req.resource_names = [route_config_name]
        response = testclient.post('/v2/discovery:routes', json=req.dict())
        data = response.json()
        assert response.status_code == 200, response.content
        assert len(data['resources']) == 1
        for route_config in data['resources']:
            assert route_config['@type'] == 'type.googleapis.com/envoy.api.v2.RouteConfiguration'
            assert route_config['name'] == route_config_name


class TestListenerDiscovery:
    def test_listeners_endpoint_returns_all_listeners(self, testclient: TestClient, discovery_request_with_auth: DiscoveryRequest):
        req = discovery_request_with_auth
        response = testclient.post('/v2/discovery:listeners', json=req.dict())
        data = response.json()
        assert response.status_code == 200, response.content
        assert len(data['resources']) == 2

    @pytest.mark.parametrize("listener_name", ('redirect_to_https', 'https_listener'))
    def test_listeners_endpoint_returns_a_specific_listener_when_requested(self, testclient: TestClient,
                                                                           discovery_request_with_auth: DiscoveryRequest,
                                                                           listener_name):
        req = discovery_request_with_auth
        req.resource_names = [listener_name]
        response = testclient.post('/v2/discovery:listeners', json=req.dict())
        data = response.json()
        assert response.status_code == 200, response.content
        assert len(data['resources']) == 1
        for listener in data['resources']:
            assert listener['@type'] == 'type.googleapis.com/envoy.api.v2.Listener'
            assert listener['name'] == listener_name


class TestClustersDiscovery:
    def test_clusters_endpoint_returns_the_configured_instance_as_an_envoy_cluster(self, testclient: TestClient,
                                                                                   discovery_request_with_auth: DiscoveryRequest, sources):
        req = discovery_request_with_auth
        # Remove this since it's not relevant for clusters, but also because it tests all paths through discovery
        del req.node.metadata['hide_private_keys']
        response = testclient.post('/v2/discovery:clusters', json=req.dict())
        data = response.json()
        assert response.status_code == 200
        assert data['resources'] == [{
            '@type': 'type.googleapis.com/envoy.api.v2.Cluster',
            'connect_timeout': '5s',
            'load_assignment': {
                'cluster_name': 'httpbin-proxy_cluster',
                'endpoints': [{
                    'lb_endpoints': [{
                        'endpoint': {
                            'address': {
                                'socket_address': {
                                    'address': 'httpbin.org',
                                    'port_value': 443}}}
                    }],
                    'locality': {'zone': 'unknown'},
                    'priority': 10
                }]},
            'name': 'httpbin-proxy',
            'tls_context': {},
            'type': 'strict_dns'
        }]

    def test_clusters_with_uptodate_config_returns_304(self, testclient: TestClient, discovery_request_with_auth: DiscoveryRequest, sources):
        req = discovery_request_with_auth
        response = testclient.post('/v2/discovery:clusters', json=req.dict())
        data = response.json()
        assert response.status_code == 200

        req = discovery_request_with_auth
        req.version_info = data['version_info']
        response = testclient.post('/v2/discovery:clusters', json=req.dict())
        assert response.text == ''
        assert response.status_code == 304

    def test_clusters_with_up_to_date_config_but_different_id_still_returns_304(self, testclient: TestClient,
                                                                                discovery_request_with_auth: DiscoveryRequest):
        req = discovery_request_with_auth
        response = testclient.post('/v2/discovery:clusters', json=req.dict())
        data = response.json()

        req = discovery_request_with_auth
        req.node.id = 'HelloWorld!:)'
        req.node.metadata['stuff'] = '1'
        req.version_info = data['version_info']
        response = testclient.post('/v2/discovery:clusters', json=req.dict())
        assert response.status_code == 304


class TestSecretDiscovery:
    def test_secrets_endpoint_provides_certificate(self, testclient: TestClient, discovery_request_with_auth: DiscoveryRequest):
        req = discovery_request_with_auth
        req.resource_names = ['certificates_1']
        response = testclient.post('/v2/discovery:secrets', json=req.dict())
        data = response.json()
        assert response.status_code == 200, response.content
        for resource in data['resources']:
            assert resource['@type'] == 'type.googleapis.com/envoy.api.v2.auth.Secret'
            assert resource['name'] == 'certificates_1'
            assert 'tls_certificate' in resource
            assert resource['tls_certificate']['private_key']['inline_string'] == 'Unavailable (No Secret Key)'

    def test_secrets_request_with_up_to_date_config_version_returns_304(self, testclient: TestClient,
                                                                        discovery_request_with_auth: DiscoveryRequest):
        req = discovery_request_with_auth
        req.resource_names = ['certificates_1']
        response = testclient.post('/v2/discovery:secrets', json=req.dict())
        data = response.json()

        req = discovery_request_with_auth
        req.resource_names = ['certificates_1']
        req.version_info = data['version_info']
        response = testclient.post('/v2/discovery:secrets', json=req.dict())
        assert response.status_code == 304, response.content

    def test_secrets_returns_404_for_a_bad_cert_name(self, testclient: TestClient, discovery_request_with_auth: DiscoveryRequest):
        req = discovery_request_with_auth
        req.resource_names = ['doesNotExist']
        response = testclient.post('/v2/discovery:secrets', json=req.dict())
        assert response.status_code == 404, response.content
        assert response.json() == {'detail': 'No resources found'}
