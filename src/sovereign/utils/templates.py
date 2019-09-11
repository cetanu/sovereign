from socket import gethostbyname_ex
from socket import gaierror as dns_error
from sovereign import statsd, config
from sovereign.decorators import memoize


@memoize(5)
def resolve(address):
    try:
        with statsd.timed('dns.resolve_ms', tags=[f'address:{address}'], use_ms=True):
            _, _, addresses = gethostbyname_ex(address)
    except dns_error:
        raise LookupError(f'Failed to resolve DNS hostname: {address}')
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
