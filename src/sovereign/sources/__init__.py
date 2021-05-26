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
from typing import Iterable, Any, Dict, List, Union, Optional, Type
from pkg_resources import iter_entry_points
from sovereign import config, get_request_id
from sovereign.modifiers import modify_sources_in_place
from sovereign.modifiers.lib import Modifier, GlobalModifier
from sovereign.statistics import stats  # type: ignore
from sovereign.schemas import (
    ConfiguredSource,
    SourceMetadata,
    SourceData,
    Node,
)
from sovereign.logs import application_log
from sovereign.sources.lib import Source

source_entry_points = iter_entry_points("sovereign.sources")
modifier_entry_points = iter_entry_points("sovereign.modifiers")
global_modifier_entrypoints = iter_entry_points("sovereign.global_modifiers")

source_metadata = SourceMetadata()
_source_data = SourceData()
_source_reference: Dict[str, Type[Source]] = {
    e.name: e.load() for e in source_entry_points
}

_loaded_modifiers: Dict[str, Type[Modifier]] = dict()
_loaded_global_modifiers: Dict[str, Type[GlobalModifier]] = dict()

node_match_key = config.matching.node_key
source_match_key = config.matching.source_key
source_refresh_rate = config.source_config.refresh_rate
matching_enabled = config.matching.enabled
debug_enabled = config.debug


if not _source_reference:
    raise RuntimeError("No sources available.")


def is_debug_request(v: str) -> bool:
    return v == "" and debug_enabled


def is_wildcard(v: List[str]) -> bool:
    return v in [["*"], "*", ("*",)]


def contains(container: Iterable[Any], item: Any) -> bool:
    return item in container


def lazy_load_modifier_entrypoints(
    entry_points: Iterable[Any], configured_modifiers: List[str]
) -> Dict[str, Union[Type[Modifier], Type[GlobalModifier]]]:
    ret = dict()
    for entry_point in entry_points:
        if entry_point.name in configured_modifiers:
            ret[entry_point.name] = entry_point.load()
    return ret


def lazy_load_modifiers() -> None:
    if len(_loaded_modifiers):
        return
    mods = lazy_load_modifier_entrypoints(modifier_entry_points, list(config.modifiers))
    for key, value in mods.items():
        if isinstance(value, Modifier):
            _loaded_modifiers[key] = value


def lazy_load_global_modifiers() -> None:
    if len(_loaded_global_modifiers):
        return
    global_modifiers = lazy_load_modifier_entrypoints(
        global_modifier_entrypoints, list(config.global_modifiers)
    )
    for key, value in global_modifiers.items():
        if isinstance(value, GlobalModifier):
            _loaded_global_modifiers[key] = value


def apply_modifications(source_data: SourceData) -> SourceData:
    """
    Wraps modify_sources_in_place so that modifier entry points
    can be lazily loaded at runtime, only when modifications are
    required/need to be executed.
    """
    lazy_load_modifiers()
    lazy_load_global_modifiers()
    return modify_sources_in_place(
        source_data,
        list(_loaded_global_modifiers.values()),
        list(_loaded_modifiers.values()),
    )


def setup_source(configured_source: ConfiguredSource) -> Source:
    """
    Takes Sources from config and turns them into Python objects, ready to use.
    """
    source_class = _source_reference[configured_source.type]
    source = source_class(
        config=configured_source.config,
        scope=configured_source.scope,
    )
    source.setup()
    return source


def sources_refresh() -> None:
    """
    All source data is stored in ``sovereign.sources._source_data``.
    Since the variable is outside this functions scope, we can only make
    in-place modifications to it via its methods.

    This function retrieves all sources, puts them into a temporary list,
    and then clears and re-fills ``_source_data`` with the new data.

    The process is done in two steps to avoid ``_source_data`` being empty
    for any significant amount of time.
    """
    stats.increment("sources.attempt")
    try:
        new_source_data = SourceData()
        for configured_source in config.sources:
            source = setup_source(configured_source)
            new_source_data.scopes[source.scope].extend(source.get())
    except Exception as e:
        application_log(
            event="Error while refreshing sources",
            traceback=[line for line in traceback.format_exc().split("\n")],
            error=e.__class__.__name__,
            detail=getattr(e, "detail", "-"),
            request_id=get_request_id(),
        )
        stats.increment("sources.error")
        raise

    if new_source_data == _source_data:
        stats.increment("sources.unchanged")
        source_metadata.update_date()
        return
    else:
        stats.increment("sources.refreshed")

    _source_data.scopes.clear()
    _source_data.scopes.update(new_source_data.scopes)
    source_metadata.update_date()
    source_metadata.update_count(
        [instance for scope in _source_data.scopes.values() for instance in scope]
    )


def read_sources() -> SourceData:
    """
    Returns a copy of source data in order to ensure it is not
    modified outside of the refresh function
    """
    return deepcopy(_source_data)


def get_instances_for_node(
    node_value: Any,
    modify: bool = True,
    sources: Optional[SourceData] = None,
) -> SourceData:
    """
    Checks a node against all sources, using the node_match_key and source_match_key
    to determine if the node should receive the source in its configuration.

    :param discovery_type: type of XDS request, used to determine if a scoped source should be evaluated
    :param node_value: value from the node portion of the envoy discovery request
    :param modify: switch to enable or disable modifications via Modifiers
    :param sources: the data sources to match the node against
    """
    if source_metadata.is_stale:
        # Log/emit metric and manually refresh sources.
        stats.increment("sources.stale")
        application_log(
            event="Sources have not been refreshed in 2 minutes",
            last_update=source_metadata.updated.isoformat(),
            instance_count=source_metadata.count,
        )
        sources_refresh()

    if sources is None:
        data: SourceData = read_sources()
    else:
        data = sources

    ret = SourceData()
    for scope, instances in data.scopes.items():
        if matching_enabled is False:
            ret.scopes[scope] = instances
            continue

        for instance in instances:
            source_value = extract_source_key(instance)

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
                ret.scopes[scope].append(instance)
    if modify:
        return apply_modifications(ret)
    return ret


def extract_node_key(node: Union[Node, Dict[Any, Any]]) -> Any:
    if "." not in node_match_key:
        # key is not nested, don't need glom
        node_value = getattr(node, node_match_key)
    else:
        try:
            node_value = glom(node, node_match_key)
        except PathAccessError:
            raise RuntimeError(
                f'Failed to find key "{node_match_key}" in discoveryRequest({node}).\n'
                f"See the docs for more info: "
                f"https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/node_matching.html"
            )
    return node_value


def extract_source_key(source: Dict[Any, Any]) -> Any:
    if "." not in source_match_key:
        # key is not nested, don't need glom
        source_value = source[source_match_key]
    else:
        try:
            source_value = glom(source, source_match_key)
        except PathAccessError:
            raise RuntimeError(
                f'Failed to find key "{source_match_key}" in instance({source}).\n'
                f"See the docs for more info: "
                f"https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/node_matching.html"
            )
    return source_value


def enumerate_source_match_keys() -> List[str]:
    """
    Checks for all match keys present in existing sources and adds them to a list

    A dict is used instead of a set because dicts cannot have duplicate keys, and
    have ordering since python 3.6
    """
    ret: Dict[str, None] = dict()
    ret["*"] = None
    for _, instances in read_sources().scopes.items():
        if matching_enabled is False:
            break

        for instance in instances:
            source_value = glom(instance, source_match_key)
            if isinstance(source_value, Iterable):
                for item in source_value:
                    ret[item] = None
                continue
            ret[source_value] = None
    return list(ret.keys())


if __name__ != "__main__":
    schedule.every(source_refresh_rate).seconds.do(sources_refresh)
