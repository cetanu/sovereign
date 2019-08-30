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
from typing import List
from pkg_resources import iter_entry_points
from sovereign import config, statsd
from sovereign.dataclasses import DiscoveryRequest, Source
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


def setup(source: Source):
    cls = _sources[source.type]
    instance = cls(source.config)
    instance.setup()
    return instance


@statsd.timed('sources.load_ms', use_ms=True)
def pull():
    for source in config.sources:
        instance = setup(source)
        yield from instance.get()


def refresh():
    with statsd.timed('sources.poll_time_ms', use_ms=True):
        new_sources = list()
        for source in pull():
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


def match_node(request: DiscoveryRequest, modify=True) -> List[dict]:
    """
    Runs all configured Sources, returning a list of the combined results

    :param request: envoy discovery request
    :param modify: switch to enable or disable modifications via Modifiers
    :return: a list of dictionaries
    """
    ret = list()
    for source in _source_data:
        source_value = source.get(config.source_match_key, [])
        node_value = getattr(request.node, config.node_match_key)

        conditions = (
            is_debug_request(node_value),
            node_value == source_value,
            node_value in source_value,
            is_wildcard(node_value),
            is_wildcard(source_value),
        )
        if any(conditions):
            ret.append(source)
    if modify:
        return apply_modifications(ret)
    return ret


if __name__ != '__main__':
    schedule.every(config.sources_refresh_rate).seconds.do(refresh)
