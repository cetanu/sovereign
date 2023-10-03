from typing import List, Optional, Any, Dict
from socket import gethostbyname_ex
from socket import gaierror as dns_error
from starlette.exceptions import HTTPException
from sovereign import config, stats

REGIONS = config.legacy_fields.regions


def resolve(address: str) -> List[str]:
    try:
        with stats.timed("dns.resolve_ms", tags=[f"address:{address}"]):
            _, _, addresses = gethostbyname_ex(address)
    except dns_error:
        raise HTTPException(
            status_code=500, detail=f"Failed to resolve DNS hostname: {address}"
        )
    else:
        return addresses


def healthchecks_enabled(healthchecks: List[Dict[str, Any]]) -> bool:
    for healthcheck in healthchecks:
        if healthcheck.get("path") in ("no", False):
            return False
    return True


def upstream_requires_tls(cluster: Dict[str, Any]) -> bool:
    for host in cluster.get("hosts", []):
        if "443" in str(host.get("port")):
            return True
    return False


def list_regions() -> Optional[List[str]]:
    return REGIONS
