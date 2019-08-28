import pytest
from sovereign.utils.weighted_clusters import (
    normalize_weights,
    round_to_100,
)


@pytest.mark.parametrize(
    "weights,normalized",
    [
        ([1, 2, 3], [16, 33, 51]),
        ([20, 25, 1], [43, 54, 3]),
        ([20, 10, 20], [40, 20, 40]),
        ([100, 100, 100], [33, 33, 34]),
        ([1, 1, 1], [33, 33, 34]),
        ([1, 1, 0], [50, 50, 0]),
        ([1, 0, 0], [100, 0, 0]),
        ([1, 0, 0, 5, 1, 7], [7, 0, 0, 35, 7, 51]),
    ]
)
def test_normalizing_cluster_weights(weights, normalized):
    actual = list(normalize_weights(weights))

    # Does the function normalize the weights?
    assert round_to_100(actual) == normalized

    # Do the normalized weights add up to 100?
    assert sum(round_to_100(actual)) == 100
