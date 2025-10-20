import pytest
from sovereign import logs, stats
from sovereign.sources import SourcePoller
from sovereign.schemas import ConfiguredSource


@pytest.mark.asyncio
async def test_source_poller():
    source = ConfiguredSource(
        type="inline",
        scope="default",
        config={
            "instances": [
                {"name": "a", "example": "foo"},
                {"name": "b", "example": "foo"},
                {"name": "c", "example": "baz"},
            ]
        },
    )
    poller = SourcePoller(
        sources=[source],
        matching_enabled=True,
        node_match_key="cluster",
        source_match_key="example",
        source_refresh_rate=10,
        logger=logs.logger,
        stats=stats,
    )
    await poller.poll()

    # Has data
    assert poller.source_data.scopes["default"] == [
        {"name": "a", "example": "foo"},
        {"name": "b", "example": "foo"},
        {"name": "c", "example": "baz"},
    ]

    # Extracts source match keys
    assert poller.match_keys == ["*", "foo", "baz"]

    # Matches accurately against one cluster
    matched = poller.match_node("foo")
    assert matched.scopes["default"] == [
        {"name": "a", "example": "foo"},
        {"name": "b", "example": "foo"},
    ]

    # Matches accurately against the other
    matched = poller.match_node("baz")
    assert matched.scopes["default"] == [
        {"name": "c", "example": "baz"},
    ]


@pytest.mark.asyncio
async def test_source_poller_retry():
    """Test that source poller retries on failure"""

    # Create a mock source that fails
    class FailingSource:
        def __init__(self, config, scope):
            self.config = config
            self.scope = scope
            self.attempt = 0

        def setup(self):
            pass

        def get(self):
            self.attempt += 1
            if self.attempt <= 2:
                raise Exception(f"Test failure {self.attempt}")
            return [{"name": "success", "attempt": self.attempt}]

    source = ConfiguredSource(
        type="inline", scope="default", config={"instances": [{"name": "test"}]}
    )

    poller = SourcePoller(
        sources=[source],
        matching_enabled=False,
        node_match_key=None,
        source_match_key=None,
        source_refresh_rate=10,
        logger=logs.logger,
        stats=stats,
    )

    # Replace source with our failing source
    failing_source = FailingSource({}, "default")
    poller.sources = [failing_source]

    # First poll should fail and increment retry count
    await poller.poll()
    assert poller.retry_count == 1
    # source_data should exist but be empty (no successful data loaded)
    assert hasattr(poller, "source_data")
    assert len(poller.source_data.scopes.get("default", [])) == 0

    # Second poll should fail again
    await poller.poll()
    assert poller.retry_count == 2

    # Third poll should succeed
    await poller.poll()
    assert poller.retry_count == 0  # Reset on success
    assert poller.source_data.scopes["default"] == [{"name": "success", "attempt": 3}]


@pytest.mark.asyncio
async def test_source_poller_max_retries():
    """Test that source poller resets retry count after max retries"""

    # Create a source that always fails
    class AlwaysFailingSource:
        def __init__(self, config, scope):
            self.config = config
            self.scope = scope

        def setup(self):
            pass

        def get(self):
            raise Exception("Always fails")

    source = ConfiguredSource(type="inline", scope="default", config={"instances": []})

    poller = SourcePoller(
        sources=[source],
        matching_enabled=False,
        node_match_key=None,
        source_match_key=None,
        source_refresh_rate=10,
        logger=logs.logger,
        stats=stats,
    )

    # Replace with always failing source
    poller.sources = [AlwaysFailingSource({}, "default")]

    # Poll until max retries
    for i in range(3):
        await poller.poll()
        if i < 2:
            assert poller.retry_count == i + 1
        else:
            # After max retries, count should reset
            assert poller.retry_count == 0


@pytest.mark.asyncio
async def test_source_poller_retry_config():
    """Test that source poller respects custom max_retries configuration"""
    from sovereign import config

    # Temporarily set custom retry config
    original_max_retries = config.source_config.max_retries
    config.source_config.max_retries = 2

    try:
        # Create failing source and poller
        class FailingSource:
            def __init__(self):
                self.scope = "default"

            def setup(self):
                pass

            def get(self):
                raise Exception("Always fails")

        poller = SourcePoller(
            sources=[
                ConfiguredSource(
                    type="inline", scope="default", config={"instances": []}
                )
            ],
            matching_enabled=False,
            node_match_key=None,
            source_match_key=None,
            source_refresh_rate=10,
            logger=logs.logger,
            stats=stats,
        )
        poller.sources = [FailingSource()]

        # Test that retry count resets after hitting custom max_retries=2
        await poller.poll()
        assert poller.retry_count == 1
        await poller.poll()
        assert poller.retry_count == 0  # Reset after max_retries=2

    finally:
        config.source_config.max_retries = original_max_retries


# TODO: test modifiers to see if they are called many times
# also think about the concept of a "cache key"
# ie. some value within the source response, which acts as a versioning number
# so that source refresh can be avoided somehow. Not sure.... need to think
# more about this.
