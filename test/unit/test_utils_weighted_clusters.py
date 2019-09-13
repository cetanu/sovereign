import pytest
from sovereign.utils.weighted_clusters import fit_weights


@pytest.mark.parametrize(
    "weights,normalized",
    [
        ([1, 2, 3], [16, 33, 51]),
        ([20, 25, 1], [43, 54, 3]),
        ([20, 10, 20], [40, 20, 40]),
        ([100, 100, 100], [33, 33, 34]),
        ([1, 1, 1], [33, 33, 34]),
        ([1, 1, 0], [50, 50, 0]),
        ([1, 1], [50, 50]),
        ([1], [100]),
        ([1, 0, 0], [100, 0, 0]),
        ([1, 0, 0, 5, 1, 7], [7, 0, 0, 35, 7, 51]),
    ]
)
def test_fitting_weighted_clusters(weights, normalized):
    weighted_clusters = [
        {'name': f'Name{weight}', 'weight': weight}
        for weight in weights
    ]
    expected = [
        {'name': f'Name{weight}', 'weight': normalized_weight}
        for weight, normalized_weight in zip(weights, normalized)
    ]
    actual = fit_weights(weighted_clusters)
    assert expected == actual
