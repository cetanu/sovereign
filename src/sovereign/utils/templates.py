from socket import gethostbyname_ex
from socket import gaierror as dns_error
from starlette.exceptions import HTTPException
from sovereign import config
from sovereign.decorators import memoize
from sovereign.statistics import stats


@memoize(5)
def resolve(address):
    try:
        with stats.timed('dns.resolve_ms', tags=[f'address:{address}']):
            _, _, addresses = gethostbyname_ex(address)
    except dns_error:
        raise HTTPException(
            status_code=500,
            detail=f'Failed to resolve DNS hostname: {address}'
        )
    else:
        return addresses


def healthchecks_enabled(healthchecks):
    for healthcheck in healthchecks:
        if healthcheck.get('path') in ('no', False):
            return False
    return True


def upstream_requires_tls(cluster):
    for host in cluster.get('hosts', []):
        if '443' in str(host.get('port')):
            return True
    return False


def list_regions():
    return config.regions
