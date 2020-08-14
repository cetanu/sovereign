from __future__ import division


def _round_to_n(sequence, n=100):
    """ Resolves issue when dividing by N results in a set of numbers that don't add up to N again

        E.g. 100 / 3 = 33
             33 * 3 = 99

        For the above example, this function returns [33, 33, 34]
     """
    if sum(sequence) == 0:
        return [0 for _ in sequence]
    if sum(sequence) != n:
        sequence[-1] = n - sum(sequence[:-1])
    return sequence


def _normalize_weights(sequence, n=100):
    total = sum(sequence)
    for item in sequence:
        try:
            yield int((item / total) * n)
        except ZeroDivisionError:
            yield 0


def fit_weights(clusters, total_weight=100):
    weights = list(_normalize_weights([cluster['weight'] for cluster in clusters], n=total_weight))
    for cluster, newly_assigned_weight in zip(clusters, _round_to_n(weights, n=total_weight)):
        cluster['weight'] = newly_assigned_weight
    return clusters
