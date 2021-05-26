import random
from betterproto import Casing
from typing import Dict, Any, Optional, List
from copy import deepcopy
from starlette.exceptions import HTTPException
from sovereign import config
from sovereign.schemas import DiscoveryRequest
from sovereign.utils.templates import resolve
from envoy_data_plane.envoy.api.v2.endpoint import LocalityLbEndpoints

HARD_FAIL_ON_DNS_FAILURE = config.legacy_fields.dns_hard_fail
PRIORITY_MAPPING = config.legacy_fields.eds_priority_matrix
TOTAL_REGIONS = len(config.legacy_fields.regions or [])
SNEK = Casing.SNAKE


def _upstream_kwargs(
    upstream: Dict[str, Any],
    proxy_region: Optional[str] = None,
    resolve_dns: bool = True,
    default_region: Optional[str] = None,
    hard_fail: Optional[bool] = HARD_FAIL_ON_DNS_FAILURE,
) -> Dict[str, Any]:
    try:
        ip_addresses = (
            resolve(upstream["address"]) if resolve_dns else [upstream["address"]]
        )
    except HTTPException:
        if hard_fail:
            raise
        ip_addresses = [upstream["address"]]
    return {
        "addrs": ip_addresses,
        "port": upstream["port"],
        "region": default_region or upstream.get("region", "unknown"),
        "zone": proxy_region,
    }


def total_zones(endpoints: List[Dict[str, Dict[str, Any]]]) -> int:
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
    zones = {e["locality"]["zone"] for e in endpoints}
    return len(zones)


def locality_lb_endpoints(
    upstreams: List[Dict[str, Any]],
    request: Optional[DiscoveryRequest] = None,
    resolve_dns: bool = True,
) -> List[Dict[str, Any]]:
    if request is None:
        proxy_region = None
    else:
        proxy_region = request.node.locality.zone

    kw_args = [_upstream_kwargs(u, proxy_region, resolve_dns) for u in upstreams]
    ret = [lb_endpoints(**kw).to_dict(casing=SNEK) for kw in kw_args]

    if total_zones(ret) == 1:
        # Pointless to do zone-aware load-balancing for a single zone
        return ret

    upstreams_copy = deepcopy(upstreams)
    while total_zones(ret) < TOTAL_REGIONS:
        region = f"zone-padding-{total_zones(ret)}"
        try:
            upstream = upstreams_copy.pop()
        except IndexError:
            # When adding zone-padding, use a randomly selected upstream
            # However, the random selection should be consistent across control-planes
            # otherwise the version_info of the response will be constantly different
            random.seed(128)
            upstream = random.choice(upstreams)
        params = _upstream_kwargs(upstream, proxy_region, resolve_dns, region)
        ret.append(lb_endpoints(**params).to_dict(casing=SNEK))
    return ret


def lb_endpoints(
    addrs: List[str], port: int, region: str, zone: str
) -> LocalityLbEndpoints:
    """
    Creates an envoy endpoint.LbEndpoints proto

    :param addrs:  The IP addresses or hostname(s) of the upstream.
    :param port:   The port that the upstream should be accessed on.
    :param region: The region of the upstream.
    :param zone:   The region of the proxy asking for the endpoint configuration.
    """
    if PRIORITY_MAPPING is None:
        raise RuntimeError(
            "Tried to create LbEndpoints using the EDS utility,"
            " but no EDS priority matrix has been specified"
        )
    node_priorities = PRIORITY_MAPPING.get(zone, {})
    priority = node_priorities.get(region, 10)
    return LocalityLbEndpoints().from_dict(
        {
            "priority": priority,
            "locality": {"zone": region},
            "lb_endpoints": [
                {
                    "endpoint": {
                        "address": {
                            "socket_address": {"address": addr, "port_value": port}
                        }
                    }
                }
                for addr in addrs
            ],
        }
    )
