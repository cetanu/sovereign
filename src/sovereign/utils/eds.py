import random
from copy import deepcopy
from starlette.exceptions import HTTPException
from sovereign import config
from sovereign.schemas import DiscoveryRequest
from sovereign.utils.templates import resolve

priority_mapping = config.eds_priority_matrix
total_regions = len(config.regions)


def _upstream_kwargs(upstream, proxy_region=None, resolve_dns=True, default_region=None, hard_fail=config.dns_hard_fail) -> dict:
    try:
        ip_addresses = resolve(upstream['address']) if resolve_dns else [upstream['address']]
    except HTTPException:
        if hard_fail:
            raise
        ip_addresses = [upstream['address']]
    return {
        'addrs': ip_addresses,
        'port': upstream['port'],
        'region': default_region or upstream.get('region', 'unknown'),
        'zone': proxy_region
    }


def total_zones(endpoints: list) -> int:
    """
    Returns the true unique number of zones, taking into account
    that multiple endpoints can have the same zone name.

    - us-west-1
    - us-west-1   == 2 zones
    - us-east-1

    - us-west-1
    - us-west-2   == 3 zones
    - us-east-2
    """
    zones = {e['locality']['zone'] for e in endpoints}
    return len(zones)


def locality_lb_endpoints(upstreams, request: DiscoveryRequest = None, resolve_dns=True):
    if request is None:
        proxy_region = None
    else:
        proxy_region = request.node.locality.zone

    kw_args = [_upstream_kwargs(u, proxy_region, resolve_dns) for u in upstreams]
    ret = [lb_endpoints(**kw) for kw in kw_args]

    if total_zones(ret) == 1:
        # Pointless to do zone-aware load-balancing for a single zone
        return ret

    upstreams_copy = deepcopy(upstreams)
    while total_zones(ret) < total_regions:
        region = f'zone-padding-{total_zones(ret)}'
        try:
            upstream = upstreams_copy.pop()
        except IndexError:
            # When adding zone-padding, use a randomly selected upstream
            # However, the random selection should be consistent across control-planes
            # otherwise the version_info of the response will be constantly different
            random.seed(128)
            upstream = random.choice(upstreams)
        kw_args = _upstream_kwargs(upstream, proxy_region, resolve_dns, region)
        ret.append(lb_endpoints(**kw_args))
    return ret


def lb_endpoints(addrs: list, port: int, region: str, zone: str = None) -> dict:
    """
    Creates an envoy endpoint.LbEndpoints proto

    :param addrs:  The IP addresses or hostname(s) of the upstream.
    :param port:   The port that the upstream should be accessed on.
    :param region: The region of the upstream.
    :param zone:   The region of the proxy asking for the endpoint configuration.
    """
    node_priorities = priority_mapping.get(zone, {})
    priority = node_priorities.get(region, 10)
    return {
        'priority': priority,
        'locality': {'zone': region},
        'lb_endpoints': [{
            'endpoint': {
                'address': {
                    'socket_address': {
                        'address': addr,
                        'port_value': port
                    }
                }
            }
        } for addr in addrs]
    }
