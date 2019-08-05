"""
Sources are used to retrieve arbitrary data that can then be represented
in templates as envoy configuration.

A new custom source can be added by subclassing the Source class and
adding an entry point using setuptools.

`todo add guide for adding entry points`

When the control plane receives a request for configuration from an envoy
proxy, it first runs through all the configured sources and combines the
data received from them into a single list, to be used within templates.

The results are cached for 30 seconds to allow several proxies to poll
at the same time, receiving data that is consistent with each other.
`todo, make the cache expiry configurable`
"""
from typing import List
from pkg_resources import iter_entry_points
from sovereign import CONFIG, DEBUG, statsd
from sovereign.logs import LOG
from sovereign.modifiers import apply_modifications

_entry_points = iter_entry_points('sovereign.sources')
_sources = {e.name: e.load() for e in _entry_points}

if not _sources:
    raise RuntimeError('No sources available.')


def load_sources(service_cluster, modify=True, debug=DEBUG) -> List[dict]:
    """
    Runs all configured Sources, returning a list of the combined results

    :param service_cluster: filter results by envoy service cluster `todo` make filtering configurable
    :param modify: switch to enable or disable modifications via Modifiers
    :param debug: switch mainly used for testing
    :return: a list of dictionaries
    """
    ret = list()
    for source in _enumerate_sources():
        if not isinstance(source, dict):
            LOG.msg('Received a non-dictionary source', level='warn', source_repr=repr(source))
            continue

        # TODO: create a 'node match' configurable option
        #       which maps between source/instance <-> node (aka envoy node)
        envoy_service_clusters = source.get('service_clusters', [])
        conditions = (
            service_cluster in envoy_service_clusters,
            envoy_service_clusters == ['*'],
            service_cluster == '' and debug
        )
        if any(conditions):
            ret.append(source)
    if modify:
        return apply_modifications(ret)
    return ret


def _enumerate_sources():
    for source in CONFIG['sources']:
        name = source['type']
        config = source['config']
        yield from _enumerate_source(name, config)


def _enumerate_source(name, conf):
    with statsd.timed('sources.load_ms', tags=[f'source_name:{name}'], use_ms=True):
        source = _sources[name]
        _source = source(conf)
        _source.setup()
        yield from _source.get()
