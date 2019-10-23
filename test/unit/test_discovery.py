import pytest
from starlette.testclient import TestClient
from sovereign import discovery, config


@pytest.mark.timeout(5)
@pytest.mark.asyncio
async def test_10000_clusters(discovery_request, sources_10000):
    config = await discovery.response(discovery_request, 'clusters')
    assert isinstance(config, dict)
    assert len(config['resources']) == 10000


@pytest.mark.timeout(0.5)
@pytest.mark.asyncio
async def test_1000_clusters(discovery_request, sources_1000):
    config = await discovery.response(discovery_request, 'clusters')
    assert isinstance(config, dict)
    assert len(config['resources']) == 1000


@pytest.mark.timeout(0.05)
@pytest.mark.asyncio
async def test_single_cluster(discovery_request, sources):
    config = await discovery.response(discovery_request, 'clusters')
    assert 'httpbin' in repr(config) and 'google-proxy' not in repr(config)


def test_discovery_with_bad_auth_should_fail_with_a_description(testclient: TestClient, discovery_request):
    req = dict(discovery_request)
    req['node']['metadata']['auth'] = 'woop de doo'
    response = testclient.post('/v2/discovery:clusters', json=req)
    assert response.status_code == 400
    assert response.json()['detail'] == 'The authentication provided was malformed [Reason: Decryption failed]'


def test_routes_endpoint_returns_all_route_configs(testclient: TestClient, discovery_request_with_auth):
    req = dict(discovery_request_with_auth)
    response = testclient.post('/v2/discovery:routes', json=req)
    data = response.json()
    assert response.status_code == 200, response.content
    assert len(data['resources']) == 1
    for route_config in data['resources']:
        assert route_config['@type'] == 'type.googleapis.com/envoy.api.v2.RouteConfiguration'
        assert route_config['name'] == 'rds'
        assert len(route_config['virtual_hosts']) == 1


@pytest.mark.parametrize("route_config_name", ['rds'])
def test_routes_endpoint_returns_specific_route_config(testclient: TestClient, discovery_request_with_auth, route_config_name):
    req = dict(discovery_request_with_auth)
    req['resource_names'] = [route_config_name]
    response = testclient.post('/v2/discovery:routes', json=req)
    data = response.json()
    assert response.status_code == 200, response.content
    assert len(data['resources']) == 1
    for route_config in data['resources']:
        assert route_config['@type'] == 'type.googleapis.com/envoy.api.v2.RouteConfiguration'
        assert route_config['name'] == route_config_name


def test_listeners_endpoint_returns_all_listeners(testclient: TestClient, discovery_request_with_auth):
    req = dict(discovery_request_with_auth)
    response = testclient.post('/v2/discovery:listeners', json=req)
    data = response.json()
    assert response.status_code == 200, response.content
    assert len(data['resources']) == 2


@pytest.mark.parametrize("listener_name", ('redirect_to_https', 'https_listener'))
def test_listeners_endpoint_returns_specific_listener(testclient: TestClient, discovery_request_with_auth, listener_name):
    req = dict(discovery_request_with_auth)
    req['resource_names'] = [listener_name]
    response = testclient.post('/v2/discovery:listeners', json=req)
    data = response.json()
    assert response.status_code == 200, response.content
    assert len(data['resources']) == 1
    for listener in data['resources']:
        assert listener['@type'] == 'type.googleapis.com/envoy.api.v2.Listener'
        assert listener['name'] == listener_name


def test_clusters(testclient: TestClient, discovery_request_with_auth, current_config, sources):
    req = dict(discovery_request_with_auth)
    # Remove this since it's not relevant for clusters, but also because it tests all paths through discovery
    del req['node']['metadata']['hide_private_keys']
    response = testclient.post('/v2/discovery:clusters', json=req)
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
    current_config['version_info'] = data['version_info']


def test_clusters_with_uptodate_config_returns_304(testclient: TestClient, discovery_request_with_auth, current_config):
    req = dict(discovery_request_with_auth)
    req['version_info'] = current_config['version_info']
    del req['node']['metadata']['hide_private_keys']
    response = testclient.post('/v2/discovery:clusters', json=req)
    assert response.json() == 'No changes'


def test_clusters_with_uptodate_config_but_different_id_still_returns_304(testclient: TestClient, discovery_request_with_auth, current_config):
    req = dict(discovery_request_with_auth)
    req['node']['id'] = 'HelloWorld!:)'
    req['node']['metadata']['stuff'] = '1'
    req['version_info'] = current_config['version_info']
    del req['node']['metadata']['hide_private_keys']
    response = testclient.post('/v2/discovery:clusters', json=req)
    assert response.json() == 'No changes'


def test_secrets_endpoint_provides_certificate(testclient: TestClient, discovery_request_with_auth, current_config):
    req = dict(discovery_request_with_auth)
    req['resource_names'] = ['certificates_1']
    response = testclient.post('/v2/discovery:secrets', json=req)
    data = response.json()
    assert response.status_code == 200, response.content
    for resource in data['resources']:
        assert resource['@type'] == 'type.googleapis.com/envoy.api.v2.auth.Secret'
        assert resource['name'] == 'certificates_1'
        assert 'tls_certificate' in resource
        assert resource['tls_certificate']['private_key']['inline_string'] == 'Unavailable (No Secret Key)'
    current_config['version_info'] = data['version_info']


def test_secrets_with_uptodate_config_returns_304(testclient: TestClient, discovery_request_with_auth, current_config):
    req = dict(discovery_request_with_auth)
    req['resource_names'] = ['certificates_1']
    req['version_info'] = current_config['version_info']
    response = testclient.post('/v2/discovery:secrets', json=req)
    assert response.status_code == config.no_changes_response_code, response.content
    assert response.json() == 'No changes'


def test_secrets_returns_404_for_bad_cert_name(testclient: TestClient, discovery_request_with_auth):
    req = dict(discovery_request_with_auth)
    req['resource_names'] = ['doesNotExist']
    response = testclient.post('/v2/discovery:secrets', json=req)
    assert response.status_code == 404, response.content
    assert response.json() == 'No resources found'
