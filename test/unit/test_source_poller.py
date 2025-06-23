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
        logger=logs,
        stats=stats,
    )
    poller.poll()

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


# TODO: test modifiers to see if they are called many times
# also think about the concept of a "cache key"
# ie. some value within the source response, which acts as a versioning number
# so that source refresh can be avoided somehow. Not sure.... need to think
# more about this.
