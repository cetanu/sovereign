import base64
import os
import random
import string
from copy import deepcopy
from unittest.mock import MagicMock

import pytest
import urllib3
from starlette.testclient import TestClient
from starlette_context import context, request_cycle_context

from sovereign import config, poller
from sovereign.app import app
from sovereign.utils.mock import mock_discovery_request

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

@pytest.fixture
def testclient():
    """
    Starlette test client which can run endpoints such as /v2/discovery:clusters
    Acts very similar to the `requests` package
    """
    return TestClient(app)


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
def discovery_request():
    """Envoy XDS Discovery request without authentication"""
    return mock_discovery_request(service_cluster="T1")


@pytest.fixture
def discovery_request_with_auth(auth_string):
    """Envoy XDS Discovery request with the test auth defined in global"""
    return mock_discovery_request(service_cluster="T1", metadata={"auth": auth_string})


@pytest.fixture
def discovery_request_with_error_detail(auth_string):
    """Envoy XDS Discovery request with error_details included"""
    return mock_discovery_request(
        service_cluster="T1",
        error_message="this is an XDS error message",
        metadata={"auth": auth_string},
    )


@pytest.fixture(autouse=True)
def mocked_context():
    with request_cycle_context({}):
        yield context
