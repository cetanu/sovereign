import pytest
import urllib3
import string
import random
from starlette.testclient import TestClient
from sovereign.app import app
from copy import deepcopy
from sovereign import config
from sovereign.schemas import Source
from sovereign.sources import sources_refresh
from sovereign.utils.mock import mock_discovery_request
from sovereign.utils.crypto import generate_key
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CURRENT_CONFIG = dict()
test_auth = 'gAAAAABdXjy8Zuf2iB5vMKlJ3qimHV7-snxrnfwYb4N' \
            'VlOwpcbYZxlNAwn5t3S3XkoTG8vB762fIogPHgUdnSs' \
            'DMDu1S1NF3Wx1HQQ9Zm2aaTYok1f380mTQOiyAcqRGr' \
            'IHYIoFXUkaA49WHMX5JfM9EBKjo3m6gPQ=='


@pytest.fixture
def testclient():
    """
    Starlette test client which can run endpoints such as /v2/discovery:clusters
    Acts very similar to the `requests` package
    """
    return TestClient(app)


orig_sources = deepcopy(config.sources)


@pytest.fixture(scope='function')
def sources():
    """ Resets the data sources back to what is configured in test/config/config.yaml """
    config.sources = orig_sources
    sources_refresh()


@pytest.fixture(scope='function')
def sources_1000():
    """ Sets the data sources to a fixture with 1,000 instances for informal stress-test """
    config.sources = [
        Source(**{
            'type': 'inline',
            'config': {
                'instances': [
                    {
                        'name': f'backend{s}',
                        'domains': [f'domain{s}'],
                        'service_clusters': ['T1'],
                        'endpoints': [
                            {
                                'address': f'fakeaddress-{n}.not-real-tld',
                                'region': 'ap-southeast-2',
                                'port': 443
                            }
                            for n in range(1, 8)
                        ]
                    }
                    for s in range(1, 1001)
                ]
            }
         })
    ]
    sources_refresh()


@pytest.fixture(scope='function')
def sources_10000():
    """ Sets the data sources to a fixture with 10,000 instances for informal stress-test """
    config.sources = [
        Source(**{
            'type': 'inline',
            'config': {
                'instances': [
                    {
                        'name': f'backend{s}',
                        'domains': [f'domain{s}'],
                        'service_clusters': ['T1'],
                        'endpoints': [
                            {
                                'address': f'fakeaddress-{n}.not-real-tld',
                                'region': 'ap-southeast-2',
                                'port': 443
                            }
                            for n in range(1, 8)
                        ]
                    }
                    for s in range(1, 10001)
                ]
            }
         })
    ]
    sources_refresh()


@pytest.fixture
def random_sovereign_key():
    """ Generates a random fernet encryption key """
    return generate_key()


@pytest.fixture
def random_string():
    """ Gives a 10kb string of random data (used for crypto tests) """
    return ''.join([
        random.choice(string.printable)
        for _ in range(1, 10240)
    ])


@pytest.fixture
def auth_string():
    """ Returns the test auth defined in global """
    return test_auth


@pytest.fixture
def discovery_request():
    """ Envoy XDS Discovery request without authentication """
    return mock_discovery_request(service_cluster='T1')


@pytest.fixture
def discovery_request_with_auth():
    """ Envoy XDS Discovery request with the test auth defined in global """
    return mock_discovery_request(service_cluster='T1', metadata={'auth': test_auth})


@pytest.fixture(autouse=True, scope='session')
def current_config():
    """
    Returns an object for the unit test session that can be modified
    to provide context to subsequent unit tests...

    Eg.
    1. We do a discovery request, we get back a version_info
    2. We set this version_info in the CURRENT_CONFIG
    3. We use the version_info in the next test
    """
    return CURRENT_CONFIG
