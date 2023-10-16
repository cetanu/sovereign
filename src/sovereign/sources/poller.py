import asyncio
import traceback
from copy import deepcopy
from importlib.metadata import EntryPoint
from datetime import timedelta, datetime
from typing import Iterable, Any, Dict, List, Union, Type, Optional

from glom import glom, PathAccessError

from sovereign.utils.entry_point_loader import EntryPointLoader
from sovereign.sources.lib import Source
from sovereign.modifiers.lib import Modifier, GlobalModifier
from sovereign.schemas import (
    ConfiguredSource,
    SourceData,
    Node,
)

from structlog.stdlib import BoundLogger


def is_debug_request(v: str, debug: bool = False) -> bool:
    return v == "" and debug


def is_wildcard(v: List[str]) -> bool:
    return v in [["*"], "*", ("*",)]


def contains(container: Iterable[Any], item: Any) -> bool:
    return item in container


Mods = Dict[str, Type[Modifier]]
GMods = Dict[str, Type[GlobalModifier]]


class SourcePoller:
    def __init__(
        self,
        sources: List[ConfiguredSource],
        matching_enabled: bool,
        node_match_key: str,
        source_match_key: str,
        source_refresh_rate: int,
        logger: BoundLogger,
        stats: Any,
    ):
        self.matching_enabled = matching_enabled
        self.node_match_key = node_match_key
        self.source_match_key = source_match_key
        self.source_refresh_rate = source_refresh_rate
        self.logger = logger
        self.stats = stats

        self.entry_points = EntryPointLoader("sources", "modifiers", "global_modifiers")

        self.source_classes: Dict[str, Type[Source]] = {
            e.name: e.load() for e in self.entry_points.groups["sources"]
        }
        self.sources = [self.setup_source(s) for s in sources]
        if not self.sources:
            raise RuntimeError("No data sources available!")

        # These have to be loaded later to avoid circular imports
        self.modifiers: Mods = dict()
        self.global_modifiers: GMods = dict()

        # initially set data and modify
        self.source_data = self.refresh()
        self.last_updated = datetime.now()
        self.instance_count = 0

    @property
    def data_is_stale(self) -> bool:
        return self.last_updated < datetime.now() - timedelta(minutes=2)

    def setup_source(self, configured_source: ConfiguredSource) -> Source:
        source_class = self.source_classes[configured_source.type]
        source = source_class(
            config=configured_source.config,
            scope=configured_source.scope,
        )
        source.setup()
        return source

    def lazy_load_modifiers(self, modifiers: List[str]) -> None:
        if len(self.modifiers) == len(modifiers):
            return
        self.modifiers = self.load_modifier_entrypoints(
            self.entry_points.groups["modifiers"], modifiers
        )

    def lazy_load_global_modifiers(self, global_modifiers: List[str]) -> None:
        if len(self.global_modifiers) == len(global_modifiers):
            return
        self.global_modifiers = self.load_global_modifier_entrypoints(
            self.entry_points.groups["global_modifiers"], global_modifiers
        )

    def load_modifier_entrypoints(
        self, entry_points: Iterable[EntryPoint], configured_modifiers: List[str]
    ) -> Dict[str, Type[Modifier]]:
        ret = dict()
        for entry_point in entry_points:
            if entry_point.name in configured_modifiers:
                self.logger.info(f"Loading modifier {entry_point.name}")
                ret[entry_point.name] = entry_point.load()
        loaded = len(ret)
        configured = len(configured_modifiers)
        assert loaded == configured, (
            f"Number of modifiers loaded ({loaded})"
            f"differ from configured: {configured_modifiers}"
        )
        return ret

    def load_global_modifier_entrypoints(
        self, entry_points: Iterable[EntryPoint], configured_modifiers: List[str]
    ) -> Dict[str, Type[GlobalModifier]]:
        ret = dict()
        for entry_point in entry_points:
            if entry_point.name in configured_modifiers:
                self.logger.info(f"Loading global modifier {entry_point.name}")
                ret[entry_point.name] = entry_point.load()

        loaded = len(ret)
        configured = len(configured_modifiers)
        assert loaded == configured, (
            f"Number of global modifiers loaded ({loaded})"
            f"differ from configured: {configured_modifiers}"
        )
        return ret

    def apply_modifications(self, data: Optional[SourceData]) -> SourceData:
        if data is None:
            data = self.source_data
        if len(self.modifiers) or len(self.global_modifiers):
            with self.stats.timed("modifiers.apply_ms"):
                data = deepcopy(data)
                for scope, instances in data.scopes.items():
                    for g in self.global_modifiers.values():
                        global_modifier = g(instances)
                        global_modifier.apply()
                        data.scopes[scope] = global_modifier.join()

                    for instance in data.scopes[scope]:
                        for m in self.modifiers.values():
                            modifier = m(instance)
                            if modifier.match():
                                # Modifies the instance in-place
                                modifier.apply()
        return data

    def refresh(self) -> SourceData:
        self.stats.increment("sources.attempt")
        try:
            new = SourceData()
            for source in self.sources:
                new.scopes[source.scope].extend(source.get())
        except Exception as e:
            self.logger.error(
                event="Error while refreshing sources",
                traceback=[line for line in traceback.format_exc().split("\n")],
                error=e.__class__.__name__,
                detail=getattr(e, "detail", "-"),
            )
            self.stats.increment("sources.error")
            raise

        # Is the new data the same as what we currently have
        if new == getattr(self, "source_data", None):
            self.stats.increment("sources.unchanged")
            self.last_updated = datetime.now()
            return self.source_data
        else:
            self.stats.increment("sources.refreshed")
            self.last_updated = datetime.now()
            self.instance_count = len(
                [instance for scope in new.scopes.values() for instance in scope]
            )
            return new

    def extract_node_key(self, node: Union[Node, Dict[Any, Any]]) -> Any:
        if "." not in self.node_match_key:
            # key is not nested, don't need glom
            node_value = getattr(node, self.node_match_key)
        else:
            try:
                node_value = glom(node, self.node_match_key)
            except PathAccessError:
                raise RuntimeError(
                    f'Failed to find key "{self.node_match_key}" in discoveryRequest({node}).\n'
                    f"See the docs for more info: "
                    f"https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/node_matching.html"
                )
        return node_value

    def extract_source_key(self, source: Dict[Any, Any]) -> Any:
        if "." not in self.source_match_key:
            # key is not nested, don't need glom
            source_value = source[self.source_match_key]
        else:
            try:
                source_value = glom(source, self.source_match_key)
            except PathAccessError:
                raise RuntimeError(
                    f'Failed to find key "{self.source_match_key}" in instance({source}).\n'
                    f"See the docs for more info: "
                    f"https://vsyrakis.bitbucket.io/sovereign/docs/html/guides/node_matching.html"
                )
        return source_value

    def match_node(
        self,
        node_value: Any,
        modify: bool = True,
    ) -> SourceData:
        """
        Checks a node against all sources, using the node_match_key and source_match_key
        to determine if the node should receive the source in its configuration.
        """

        if self.data_is_stale:
            # Log/emit metric and manually refresh sources.
            self.stats.increment("sources.stale")
            self.logger.debug(
                "Sources have not been refreshed in 2 minutes",
                last_update=self.last_updated,
                instance_count=self.instance_count,
            )
            self.poll()

        ret = SourceData()

        if modify:
            if not hasattr(self, "source_data_modified"):
                self.poll()
            data = self.source_data_modified
        else:
            data = self.source_data

        for scope, instances in data.scopes.items():
            if self.matching_enabled is False:
                ret.scopes[scope] = instances
                continue

            for instance in instances:
                source_value = self.extract_source_key(instance)

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
        return ret

    @property
    def match_keys(self) -> List[str]:
        """
        Checks for all match keys present in existing sources and adds them to a list

        A dict is used instead of a set because dicts cannot have duplicate keys, and
        have ordering since python 3.6
        """
        ret: Dict[str, None] = dict()
        ret["*"] = None
        for _, instances in self.source_data.scopes.items():
            if self.matching_enabled is False:
                break
            for instance in instances:
                source_value = glom(instance, self.source_match_key)
                if isinstance(source_value, str):
                    ret[source_value] = None
                elif isinstance(source_value, Iterable):
                    for item in source_value:
                        ret[item] = None
                    continue
                ret[source_value] = None
        return list(ret.keys())

    def poll(self) -> None:
        self.source_data = self.refresh()
        self.source_data_modified = self.apply_modifications(self.source_data)

    async def poll_forever(self) -> None:
        while True:
            self.poll()
            await asyncio.sleep(self.source_refresh_rate)
