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
import traceback
from glom import glom, PathAccessError
from copy import deepcopy
from typing import List, Iterable
from pkg_resources import iter_entry_points
from sovereign import config
from sovereign.middlewares import get_request_id
from sovereign.statistics import stats
from sovereign.schemas import DiscoveryRequest, Source, SourceMetadata
from sovereign.logs import LOG
from sovereign.modifiers import apply_modifications
from sovereign.decorators import memoize

_metadata = SourceMetadata()
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
    stats.increment('sources.attempt')
    try:
        new_sources = list()
        for source in pull_sources():
            if not isinstance(source, dict):
                LOG.warn('Received a non-dictionary source', source_repr=repr(source))
                continue
            new_sources.append(source)
    except Exception as e:
        LOG.error(
            'Error while refreshing sources',
            traceback=[line for line in traceback.format_exc().split('\n')],
            error=e.__class__.__name__,
            detail=getattr(e, 'detail', '-'),
            request_id=get_request_id()
        )
        stats.increment('sources.error')
        raise

    if new_sources == _source_data:
        stats.increment('sources.unchanged')
        _metadata.update_date()
        return
    else:
        stats.increment('sources.refreshed')

    _source_data.clear()
    _source_data.extend(new_sources)
    _metadata.update_date()
    _metadata.update_count(_source_data)


@memoize(config.sources_refresh_rate * 0.8)
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
    if _metadata.is_stale:
        # Log/emit metric and manually refresh sources.
        stats.increment('sources.stale')
        LOG.warn(
            'Sources have not been refreshed in 2 minutes',
            last_update=_metadata.updated,
            instance_count=_metadata.count
        )
        sources_refresh()

    ret = list()
    for source in read_sources():
        if config.node_matching is False:
            ret.append(source)
            continue

        source_value = extract_source_key(source)
        node_value = extract_node_key(request)

        # If a single expression evaluates true, the remaining are not evaluated/executed.
        # This saves (a small amount of) computation, which helps when the server starts
        # to receive thousands of requests. The list has been ordered descending by what
        # we think will more commonly be true.
        match = (
            contains(source_value, node_value)
            or node_value == source_value
            or is_wildcard(node_value)
            or is_wildcard(source_value)
            or is_debug_request(node_value)
        )
        if match:
            ret.append(source)
    if modify:
        return apply_modifications(ret)
    return ret


def extract_node_key(request):
    if '.' not in config.node_match_key:
        # key is not nested, don't need glom
        node_value = getattr(request.node, config.node_match_key)
    else:
        try:
            node_value = glom(request.node, config.node_match_key)
        except PathAccessError:
            raise RuntimeError(
                f'Failed to find key "{config.node_match_key}" in discoveryRequest({request.node}).\n'
                f'See the docs for more info: '
                f'https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/node_matching.html'
            )
    return node_value


def extract_source_key(source):
    if '.' not in config.source_match_key:
        # key is not nested, don't need glom
        source_value = source[config.source_match_key]
    else:
        try:
            source_value = glom(source, config.source_match_key)
        except PathAccessError:
            raise RuntimeError(
                f'Failed to find key "{config.source_match_key}" in instance({source}).\n'
                f'See the docs for more info: '
                f'https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/node_matching.html'
            )
    return source_value


def available_service_clusters():
    """
    Checks for all match keys present in existing sources and adds them to a list

    A dict is used instead of a set because dicts cannot have duplicate keys, and
    have ordering since python 3.6
    """
    ret = dict()
    ret['*'] = None
    for source in read_sources():
        source_value = glom(source, config.source_match_key)
        if isinstance(source_value, Iterable):
            for item in source_value:
                ret[item] = None
            continue
        ret[source_value] = None
    return list(ret.keys())


if __name__ != '__main__':
    schedule.every(config.sources_refresh_rate).seconds.do(sources_refresh)
