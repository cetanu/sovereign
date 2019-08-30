import pytest
import urllib3
import string
import random
from sovereign.utils.mock import mock_discovery_request
from sovereign.utils.crypto import generate_key
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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
    return 'gAAAAABdXjy8Zuf2iB5vMKlJ3qimHV7-snxrnfwYb4N' \
           'VlOwpcbYZxlNAwn5t3S3XkoTG8vB762fIogPHgUdnSs' \
           'DMDu1S1NF3Wx1HQQ9Zm2aaTYok1f380mTQOiyAcqRGr' \
           'IHYIoFXUkaA49WHMX5JfM9EBKjo3m6gPQ=='


@pytest.fixture
def discovery_request():
    return mock_discovery_request(service_cluster='')
