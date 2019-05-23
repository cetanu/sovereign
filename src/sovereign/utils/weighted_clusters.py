from __future__ import division

def round_to_100(sequence):
    """ Resolves issue when dividing 100 results in a set of numbers that don't add up to 100 again

        E.g. 100 / 3 = 33
             33 * 3 = 99

        For the above example, this function returns [33, 33, 34]
     """
    if sum(sequence) != 100:
        sequence[-1] = 100 - sum(sequence[:-1])
    return sequence


def fit_weights(clusters):
    weights = [cluster['weight'] for cluster in clusters]
    for cluster, newly_assigned_weight in zip(clusters, round_to_100(weights)):
        cluster['weight'] = newly_assigned_weight
    return clusters


def normalize_weights(sequence):
    total = sum(sequence)
    for item in sequence:
        yield int((item / total) * 100)
