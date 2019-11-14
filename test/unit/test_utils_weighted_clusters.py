import pytest
from sovereign.utils.weighted_clusters import fit_weights


@pytest.mark.parametrize(
    "weights,normalized",
    [
        pytest.param([1, 2, 3], [16, 33, 51]                 , id='1, 2, 3'),
        pytest.param([20, 25, 1], [43, 54, 3]                , id='20, 25, 1'),
        pytest.param([20, 10, 20], [40, 20, 40]              , id='20, 10, 20'),
        pytest.param([100, 100, 100], [33, 33, 34]           , id='100, 100, 100'),
        pytest.param([1, 1, 1], [33, 33, 34]                 , id='1, 1, 1'),
        pytest.param([1, 1, 0], [50, 50, 0]                  , id='1, 1, 0'),
        pytest.param([1, 1], [50, 50]                        , id='1, 1'),
        pytest.param([1], [100]                              , id='1'),
        pytest.param([1, 0, 0], [100, 0, 0]                  , id='1, 0, 0'),
        pytest.param([1, 0, 0, 5, 1, 7], [7, 0, 0, 35, 7, 51], id='1, 0, 0, 5, 1, 7'),
    ]
)
def test_cluster_weights_normalize__and_add_up_to_a_total_weight_of_100(weights, normalized):
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
