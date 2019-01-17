from socket import gethostbyname_ex
from socket import gaierror as dns_error
from werkzeug.exceptions import Gone
from sovereign import CONFIG, statsd
from sovereign.decorators import memoize


@memoize(5)
def resolve(address):
    try:
        with statsd.timed('dns.resolve_ms', tags=[f'address:{address}'], use_ms=True):
            _, _, addresses = gethostbyname_ex(address)
    except dns_error:
        raise Gone(f'Failed to resolve DNS hostname: {address}')
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
    return CONFIG.get('regions', [])


def remove_tls_certificates(listener):
    for filter_chain in listener['filter_chains']:
        try:
            # Traverse down, each line separate for easier debugging
            tls_context = filter_chain['tls_context']
            common_tls_context = tls_context['common_tls_context']
            tls_certificates = common_tls_context['tls_certificates']
        except KeyError:
            pass
        else:
            for certificate in tls_certificates:
                certificate['private_key'] = {'inline_string': '<REDACTED>'}
