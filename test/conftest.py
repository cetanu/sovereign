import pytest
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@pytest.fixture
def discovery_request():
    return {
        'node': {
            # This will select any cluster
            'cluster': ''
        },
        'version_info': '0'
    }


@pytest.fixture
def filter_chain_tls_input():
    return {
        'filter_chains': [{
            'tls_context': {
                'common_tls_context': {
                    'tls_certificates': [{
                        'public_key': {'inline_string': 'hello'},
                        'private_key': {'inline_string': 'hello'},
                    }]
                }
            }
        }]
    }


@pytest.fixture
def filter_chain_tls_expected():
    return {
        'filter_chains': [{
            'tls_context': {
                'common_tls_context': {
                    'tls_certificates': [{
                        'public_key': {'inline_string': 'hello'},
                        'private_key': {'inline_string': '<REDACTED>'},
                    }]
                }
            }
        }]
    }
