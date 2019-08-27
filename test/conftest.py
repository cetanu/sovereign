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
