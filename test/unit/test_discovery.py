from starlette.testclient import TestClient
from sovereign import config


def test_clusters(testclient: TestClient, discovery_request_with_auth):
    response = testclient.post('/v2/discovery:clusters', json=dict(discovery_request_with_auth))
    assert response.status_code == 200
    assert response.json() == {
        'resources': [{
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
        }],
        'version_info': '1622641230'
    }


def test_clusters_with_uptodate_config_returns_304(testclient: TestClient, discovery_request_with_auth):
    req = dict(discovery_request_with_auth)
    req['version_info'] = '1622641230'
    response = testclient.post('/v2/discovery:clusters', json=req)
    assert response.status_code == config.no_changes_response_code
    assert response.json() == 'No changes'
