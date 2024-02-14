import base64
import os
import random
import string
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
import urllib3
from starlette.testclient import TestClient

from sovereign import config, poller
from sovereign.app import app
from sovereign.utils.mock import mock_discovery_request

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

test_auth = (
    "gAAAAABdXjy8Zuf2iB5vMKlJ3qimHV7-snxrnfwYb4N"
    "VlOwpcbYZxlNAwn5t3S3XkoTG8vB762fIogPHgUdnSs"
    "DMDu1S1NF3Wx1HQQ9Zm2aaTYok1f380mTQOiyAcqRGr"
    "IHYIoFXUkaA49WHMX5JfM9EBKjo3m6gPQ=="
)


def pytest_configure(config):
    config.addinivalue_line("markers", "all")
    envoy_versions = [
        (1, min_, patch_) for min_ in range(8, 19) for patch_ in range(0, 10)
    ]
    version_fmt = "v{major}_{minor}_{patch}"
    for major, minor, patch in envoy_versions:
        version = version_fmt.format(major=major, minor=minor, patch=patch)
        config.addinivalue_line("markers", version)


@pytest.fixture
def testclient():
    """
    Starlette test client which can run endpoints such as /v2/discovery:clusters
    Acts very similar to the `requests` package
    """
    return TestClient(app)


@pytest.fixture(scope="session")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"


@pytest.fixture(scope="session")
def mock_logger():
    return MagicMock()


orig_sources = deepcopy(config.sources)


@pytest.fixture(scope="function")
def sources():
    """Resets the data sources back to what is configured in test/config/config.yaml"""
    config.sources = orig_sources
    poller.refresh()


@pytest.fixture(scope="session")
def random_sovereign_key_func():
    """Generates a random encryption key for fernet or aesgcm"""
    return lambda: base64.urlsafe_b64encode(os.urandom(32)).decode()


@pytest.fixture
def random_string():
    """Gives a 10kb string of random data (used for crypto tests)"""
    return "".join([random.choice(string.printable) for _ in range(1, 10240)])


@pytest.fixture
def auth_string():
    """Returns the test auth defined in global"""
    return test_auth


@pytest.fixture
def discovery_request():
    """Envoy XDS Discovery request without authentication"""
    return mock_discovery_request(service_cluster="T1")


@pytest.fixture
def discovery_request_with_auth():
    """Envoy XDS Discovery request with the test auth defined in global"""
    return mock_discovery_request(service_cluster="T1", metadata={"auth": test_auth})


@pytest.fixture
def discovery_request_with_error_detail():
    """Envoy XDS Discovery request with error_details included"""
    return mock_discovery_request(
        service_cluster="T1",
        error_message="this is an XDS error message",
        metadata={"auth": test_auth},
    )
