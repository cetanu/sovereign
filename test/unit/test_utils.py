import yaml
import pytest
from sovereign.utils.weighted_clusters import (
    normalize_weights,
    round_to_100,
)
from sovereign.utils.templates import (
    remove_tls_certificates,
    list_regions
)
from sovereign.utils.eds import locality_lb_endpoints
from sovereign.decorators import memoize


def test_memoize_decorator():
    """ We know the decorator works because the inside function is only called once. """

    def inner():
        inner.calls = getattr(inner, 'calls', 0)
        inner.calls += 1
        return 'hello'

    @memoize(5)
    def cached_function():
        return inner()

    for _ in range(100):
        cached_function()

    assert inner.calls == 1


def test_removing_tls_certs(filter_chain_tls_input, filter_chain_tls_expected):
    remove_tls_certificates(filter_chain_tls_input)
    assert filter_chain_tls_input == filter_chain_tls_expected


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


@pytest.mark.timeout(5)
def test_endpoint_zone_padding():
    configs = list()

    configs.append("""
    - address: google.com
      port: 443
      proto: TCP
      region: us-west-2
    - address: google.com
      port: 443
      proto: TCP
      region: us-west-1
    """)

    configs.append("""
    - address: google.com
      port: 443
      proto: TCP
      region: us-west-2
    - address: facebook.com
      port: 443
      proto: TCP
      region: us-west-1
    - address: amazon.com
      port: 443
      proto: TCP
      region: us-west-1
    """)

    for config in configs:
        hosts = yaml.load(config)
        actual = {e['locality']['zone'] for e in locality_lb_endpoints(hosts, resolve_dns=False)}
        zones = list_regions()
        assert len(zones) == len(actual)


@pytest.mark.timeout(5)
def test_endpoints_are_deterministic():
    config = yaml.load("""
    - address: google.com
      port: 443
      proto: TCP
      region: us-west-2
    - address: facebook.com
      port: 443
      proto: TCP
      region: us-west-1
    - address: amazon.com
      port: 443
      proto: TCP
      region: us-west-1
    - address: amazon.com
      port: 443
      proto: TCP
      region: us-west-1
    - address: atlassian.com
      port: 443
      proto: TCP
      region: us-west-1
    - address: www.atlassian.com
      port: 443
      proto: TCP
      region: us-west-1
    """)

    for _ in range(50):
        a = locality_lb_endpoints(config, resolve_dns=False)
        b = locality_lb_endpoints(config, resolve_dns=False)
        c = locality_lb_endpoints(config, resolve_dns=False)
        d = locality_lb_endpoints(config, resolve_dns=False)
        e = locality_lb_endpoints(config, resolve_dns=False)
        assert a == b == c == d == e
