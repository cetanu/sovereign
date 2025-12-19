import base64
import os
import random
import string
import tempfile
from copy import deepcopy
from unittest.mock import MagicMock

import boto3
import pytest
import urllib3
from moto import mock_s3
from starlette.testclient import TestClient
from starlette_context import context, request_cycle_context

from sovereign.cache.types import Entry
from sovereign.configuration import config
from sovereign.types import Node
from sovereign.utils.mock import mock_discovery_request

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@pytest.fixture
def generic_error_response():
    with mock_s3():
        from sovereign.app import generic_error_response

        return generic_error_response


@pytest.fixture
def testclient():
    """
    Starlette test client which can run endpoints such as /v2/discovery:clusters
    Acts very similar to the `requests` package
    """
    with mock_s3():
        from sovereign.app import app

        return TestClient(app)


@pytest.fixture(scope="session")
def mock_logger():
    return MagicMock()


orig_sources = deepcopy(config.sources)


@pytest.fixture(scope="function")
def sources():
    """Resets the data sources back to what is configured in test/config/config.yaml"""
    config.sources = orig_sources
    with mock_s3():
        from sovereign.worker import poller

        poller.lazy_load_modifiers(config.modifiers)
        poller.lazy_load_global_modifiers(config.global_modifiers)
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
    return mock_discovery_request(expressions=["cluster=T1"])


@pytest.fixture
def discovery_request_with_auth(auth_string):
    """Envoy XDS Discovery request with the test auth defined in global"""
    return mock_discovery_request(
        expressions=[f"cluster=T1 metadata.auth={auth_string}"]
    )


@pytest.fixture
def discovery_request_with_error_detail(auth_string):
    """Envoy XDS Discovery request with error_details included"""
    return mock_discovery_request(
        expressions=[f"cluster=T1 metadata.auth={auth_string}"],
        error_message="this is an XDS error message",
    )


@pytest.fixture(autouse=True)
def mocked_context():
    with request_cycle_context({}):
        yield context


# ============================================================================
# Shared Cache Testing Fixtures
# ============================================================================


@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for filesystem cache tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_s3_bucket():
    """Set up a mocked S3 bucket for cache backend tests.

    Yields a dict with bucket_name, prefix, and s3 client.
    """
    with mock_s3():
        bucket_name = "test-cache-bucket"
        prefix = "sovereign-cache"
        s3_client = boto3.client("s3", region_name="us-east-1")
        s3_client.create_bucket(Bucket=bucket_name)
        yield {"bucket_name": bucket_name, "prefix": prefix, "client": s3_client}


@pytest.fixture
def mock_cache_entry():
    """Create a mock cache Entry for testing."""
    return Entry(
        text='{"resources": [{"name": "test_resource"}]}',
        len=1,
        version="test_v1",
        node=Node(cluster="test-cluster"),
    )


@pytest.fixture
def mock_cache_discovery_request():
    """Create a mock DiscoveryRequest for cache tests."""
    return mock_discovery_request(
        api_version="v3",
        resource_type="clusters",
        expressions=["cluster=test-cluster"],
    )
