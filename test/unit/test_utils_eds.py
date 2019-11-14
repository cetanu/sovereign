import yaml

from sovereign import config
from sovereign.utils.eds import locality_lb_endpoints


def test_eds_utility_adds_padding_to_zones_with_multiple_regions():
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

    for c in configs:
        hosts = yaml.safe_load(c)
        actual = {e['locality']['zone'] for e in locality_lb_endpoints(hosts, resolve_dns=False)}
        zones = config.regions
        assert len(zones) == len(actual)


def test_generated_endpoints_are_deterministic_and_sorted():
    config = yaml.safe_load("""
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
