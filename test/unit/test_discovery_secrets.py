from starlette.testclient import TestClient
from sovereign import config


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
