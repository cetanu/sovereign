import os
import urllib3

import pytest

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def pytest_configure(config):
    config.addinivalue_line("markers", "all")
    envoy_versions = [
        (1, min_, patch_) for min_ in range(8, 19) for patch_ in range(0, 10)
    ]
    version_fmt = "v{major}_{minor}_{patch}"
    for major, minor, patch in envoy_versions:
        version = version_fmt.format(major=major, minor=minor, patch=patch)
        config.addinivalue_line("markers", version)


@pytest.fixture(scope="session")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"


@pytest.fixture
def auth_string():
    """Returns the test auth defined in global"""
    return (
        "gAAAAABdXjy8Zuf2iB5vMKlJ3qimHV7-snxrnfwYb4N"
        "VlOwpcbYZxlNAwn5t3S3XkoTG8vB762fIogPHgUdnSs"
        "DMDu1S1NF3Wx1HQQ9Zm2aaTYok1f380mTQOiyAcqRGr"
        "IHYIoFXUkaA49WHMX5JfM9EBKjo3m6gPQ=="
    )
