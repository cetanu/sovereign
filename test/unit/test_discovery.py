import pytest
from sovereign import discovery


@pytest.mark.asyncio
async def test_discovery(discovery_request, sources):
    config = await discovery.response(discovery_request, 'clusters')
    assert 'httpbin' in repr(config) and 'google-proxy' not in repr(config)


@pytest.mark.asyncio
async def test_discovery_1000(discovery_request, sources_1000):
    config = await discovery.response(discovery_request, 'clusters')
    assert isinstance(config, dict)
    assert len(config['resources']) == 1000


@pytest.mark.asyncio
async def test_discovery_10000(discovery_request, sources_10000):
    config = await discovery.response(discovery_request, 'clusters')
    assert isinstance(config, dict)
    assert len(config['resources']) == 10000
