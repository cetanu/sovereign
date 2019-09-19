"""
Sources are used to retrieve arbitrary data that can then be represented
in templates as envoy configuration.

A new custom source can be added by subclassing the Source class and
adding an entry point using setuptools.

`todo add guide for adding entry points`

When the control plane receives a request for configuration from an envoy
proxy, it first runs through all the configured sources and combines the
data received from them into a single list, to be used within templates.

The results are cached for a configurable number of seconds to allow several proxies to poll
at the same time, receiving data that is consistent with each other.
"""
import schedule
from glom import glom
from copy import deepcopy
from typing import List, Iterable
from pkg_resources import iter_entry_points
from sovereign import config, statsd
from sovereign.schemas import DiscoveryRequest, Source
from sovereign.logs import LOG
from sovereign.modifiers import apply_modifications

_source_data = list()
_entry_points = iter_entry_points('sovereign.sources')
_sources = {e.name: e.load() for e in _entry_points}

if not _sources:
    raise RuntimeError('No sources available.')


def is_debug_request(v):
    return v == '' and config.debug_enabled


def is_wildcard(v):
    return v in [['*'], '*', ('*',)]


def contains(container, item):
    if isinstance(container, Iterable):
        return item in container


def setup_sources(source: Source):
    """
    Takes Sources from config and turns them into Python objects, ready to use.
    """
    cls = _sources[source.type]
    instance = cls(source.config)
    instance.setup()
    return instance


def pull_sources():
    """
    Runs .get() on every configured Source; returns the results in a generator.
    """
    for source in config.sources:
        instance = setup_sources(source)
        yield from instance.get()


def sources_refresh():
    """
    All source data is stored in ``sovereign.sources._source_data``.
    Since the variable is outside this functions scope, we can only make
    in-place modifications to it via its methods.

    This function retrieves all sources, puts them into a temporary list,
    and then clears and re-fills ``_source_data`` with the new data.

    The process is done in two steps to avoid ``_source_data`` being empty
    for any significant amount of time.
    """
    with statsd.timed('sources.poll_time_ms', use_ms=True):
        new_sources = list()
        for source in pull_sources():
            if not isinstance(source, dict):
                LOG.msg('Received a non-dictionary source', level='warn', source_repr=repr(source))
                continue
            new_sources.append(source)

    if new_sources == _source_data:
        statsd.increment('sources.unchanged')
        return
    else:
        statsd.increment('sources.refreshed')

    with statsd.timed('sources.swap_time_ms', use_ms=True):
        _source_data.clear()
        _source_data.extend(new_sources)
    return


def read_sources():
    """
    Returns a copy of source data in order to ensure it is not
    modified outside of the refresh function
    """
    return deepcopy(_source_data)


def match_node(request: DiscoveryRequest, modify=True) -> List[dict]:
    """
    Checks a node against all sources, using the node_match_key and source_match_key
    to determine if the node should receive the source in its configuration.

    :param request: envoy discovery request
    :param modify: switch to enable or disable modifications via Modifiers
    """
    ret = list()
    for source in read_sources():
        source_value = glom(source, config.source_match_key)
        node_value = glom(request.node, config.node_match_key)

        conditions = (
            is_debug_request(node_value),
            node_value == source_value,
            contains(source_value, node_value),
            is_wildcard(node_value),
            is_wildcard(source_value),
            config.node_matching is False
        )
        if any(conditions):
            ret.append(source)
    if modify:
        return apply_modifications(ret)
    return ret


if __name__ != '__main__':
    schedule.every(config.sources_refresh_rate).seconds.do(sources_refresh)
