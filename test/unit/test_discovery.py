import pytest
from sovereign import discovery


@pytest.mark.timeout(0.1)
@pytest.mark.asyncio
async def test_discovery(discovery_request, sources):
    config = await discovery.response(discovery_request, 'clusters')
    assert config['version_info'] == '1025802682'


@pytest.mark.timeout(15)
@pytest.mark.asyncio
async def test_discovery_extensive(discovery_request, extensive_sources):
    config = await discovery.response(discovery_request, 'clusters')
    assert config['version_info'] == '2019305040'
