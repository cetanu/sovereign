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
    return TestClient(app)

orig_sources = deepcopy(config.sources)


@pytest.fixture(scope='function')
def sources():
    config.sources = orig_sources
    sources_refresh()


@pytest.fixture(scope='function')
def sources_1000():
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
    return generate_key()


@pytest.fixture
def random_string():
    return ''.join([
        random.choice(string.printable)
        for _ in range(1, 10240)
    ])


@pytest.fixture
def auth_string():
    return test_auth


@pytest.fixture
def discovery_request():
    return mock_discovery_request(service_cluster='T1')


@pytest.fixture
def discovery_request_with_auth():
    return mock_discovery_request(service_cluster='T1', metadata={'auth': test_auth})


@pytest.fixture(autouse=True, scope='session')
def current_config():
    return CURRENT_CONFIG
