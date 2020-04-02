import pytest
from starlette.testclient import TestClient


def test_xds_dump_endpoint_requires_a_type(testclient: TestClient):
    response = testclient.get('/admin/xds_dump')
    assert response.status_code == 422
    assert response.json() == {
        'detail': [{'loc': ['query', 'xds_type'],
                    'msg': 'field required',
                    'type': 'value_error.missing'}]
    }


@pytest.mark.parametrize("xds_type", ('clusters', 'routes', 'listeners', 'endpoints', 'secrets'))
def test_xds_dump_endpoint_doesnt_result_in_an_error(testclient: TestClient, xds_type):
    response = testclient.get(f'/admin/xds_dump?xds_type={xds_type}')
    assert response.status_code == 200


def test_source_dump_endpoint_doesnt_result_in_an_error(testclient: TestClient):
    response = testclient.get('/admin/source_dump')
    assert response.status_code == 200
    assert response.json() == {
        'scopes': {
            'listeners': [
                {
                    'name': 'ssh',
                    'port': 22,
                    'tcp': True,
                    'target': 'httpbin-proxy',
                    'service_clusters': ['T1']
                }
            ],
            'default': [
                {
                    'name': 'google-proxy',
                    'service_clusters': ['X1'],
                    'endpoints': [
                        {'address': 'google.com.au', 'region': 'ap-southeast-2', 'port': 443},
                        {'address': 'google.com', 'region': 'us-west-1', 'port': 443},
                    ],
                    'domains': ['google.local']
                },
                {
                    'name': 'httpbin-proxy',
                    'service_clusters': ['T1'],
                    'endpoints': [
                        {'address': 'httpbin.org', 'port': 443},
                    ],
                    'domains': ['example.local']
                }
            ]
        }
    }


@pytest.mark.xfail
def test_config_dump_shows_everything_except_sensitive_fields(testclient: TestClient):
    response = testclient.get('/admin/config')
    assert response.status_code == 200
    cfg = response.json()
    assert cfg['auth_passwords'] == 'redacted'
    assert cfg['sentry_dsn'] == 'redacted'
    assert cfg['encryption_key'] == 'redacted'
