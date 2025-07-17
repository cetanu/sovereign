import json
import uuid
import asyncio
import traceback
from copy import deepcopy
from importlib.metadata import EntryPoint
from datetime import timedelta, datetime
from typing import Iterable, Any, Dict, List, Union, Type, Optional

from glom import glom, PathAccessError

from sovereign.schemas import ConfiguredSource, SourceData, Node, config
from sovereign.utils.entry_point_loader import EntryPointLoader
from sovereign.sources.lib import Source
from sovereign.modifiers.lib import Modifier, GlobalModifier
from sovereign.context import NEW_CONTEXT

from structlog.stdlib import BoundLogger


def is_debug_request(v: str, debug: bool = False) -> bool:
    return v == "" and debug


def is_wildcard(v: List[str]) -> bool:
    return v in [["*"], "*", ("*",)]


def contains(container: Iterable[Any], item: Any) -> bool:
    return item in container


Mods = Dict[str, Type[Modifier]]
GMods = Dict[str, Type[GlobalModifier]]


def _deep_diff(old, new, path="") -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []

    # handle add/remove
    if (old, new) == (None, None):
        return changes
    elif old is None:
        changes.append({"op": "add", "path": path, "value": new})
        return changes
    elif new is None:
        changes.append({"op": "remove", "path": path, "old_value": old})
        return changes

    # handle completely different types
    if type(old) is not type(new):
        changes.append(
            {"op": "change", "path": path, "old_value": old, "new_value": new}
        )
        return changes

    # handle fields recursively
    if isinstance(old, dict) and isinstance(new, dict):
        all_keys = set(old.keys()) | set(new.keys())

        for key in sorted(all_keys):
            old_val = old.get(key)
            new_val = new.get(key)

            current_path = f"{path}.{key}" if path else key

            if key not in old:
                changes.append({"op": "add", "path": current_path, "value": new_val})
            elif key not in new:
                changes.append(
                    {"op": "remove", "path": current_path, "old_value": old_val}
                )
            elif old_val != new_val:
                nested_changes = _deep_diff(old_val, new_val, current_path)
                changes.extend(nested_changes)

    # handle items recursively
    elif isinstance(old, list) and isinstance(new, list):
        max_len = max(len(old), len(new))

        for i in range(max_len):
            current_path = f"{path}[{i}]" if path else f"[{i}]"

            if i >= len(old):
                changes.append({"op": "add", "path": current_path, "value": new[i]})
            elif i >= len(new):
                changes.append(
                    {"op": "remove", "path": current_path, "old_value": old[i]}
                )
            elif old[i] != new[i]:
                nested_changes = _deep_diff(old[i], new[i], current_path)
                changes.extend(nested_changes)

    # handle primitives
    else:
        if old != new:
            changes.append(
                {"op": "change", "path": path, "old_value": old, "new_value": new}
            )

    return changes


def per_field_diff(old, new) -> list[dict[str, Any]]:
    changes = []
    max_len = max(len(old), len(new))

    for i in range(max_len):
        old_inst = old[i] if i < len(old) else None
        new_inst = new[i] if i < len(new) else None

        if old_inst is None:
            changes.append({"op": "add", "path": f"[{i}]", "value": new_inst})
        elif new_inst is None:
            changes.append({"op": "remove", "path": f"[{i}]", "old_value": old_inst})
        elif old_inst != new_inst:
            # Use the deep diff with index prefix
            field_changes = _deep_diff(old_inst, new_inst, f"[{i}]")
            changes.extend(field_changes)

    return changes


def _gen_uuid(diff_summary: dict[str, Any]) -> str:
    blob = json.dumps(diff_summary, sort_keys=True, separators=("", ""))
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, blob))


def source_diff_summary(prev, curr) -> dict[str, Any]:
    if prev is None:
        summary = {
            "type": "initial_load",
            "scopes": {
                scope: {"added": len(instances)}
                for scope, instances in curr.scopes.items()
                if instances
            },
        }
    else:
        summary = {"type": "update", "scopes": {}}

        all_scopes = set(prev.scopes.keys()) | set(curr.scopes.keys())

        for scope in sorted(all_scopes):
            old = prev.scopes.get(scope, [])
            new = curr.scopes.get(scope, [])

            n_old = len(old)
            n_new = len(new)

            scope_changes: dict[str, Any] = {}

            if n_old == 0 and n_new > 0:
                scope_changes["added"] = n_new
            elif n_old > 0 and n_new == 0:
                scope_changes["removed"] = n_old
            elif old != new:
                detailed_changes = per_field_diff(old, new)
                if detailed_changes:
                    scope_changes["field_changes"] = detailed_changes
                    scope_changes["count_change"] = n_new - n_old

            if scope_changes:
                summary["scopes"][scope] = scope_changes  # type: ignore

        if not summary["scopes"]:
            summary = {"type": "no_changes"}

    summary["uuid"] = _gen_uuid(summary)
    return summary


class SourcePoller:
    def __init__(
        self,
        sources: List[ConfiguredSource],
        matching_enabled: bool,
        node_match_key: Optional[str],
        source_match_key: Optional[str],
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
        self.source_data: SourceData = SourceData()
        self.source_data_modified: SourceData = SourceData()
        self.last_updated = datetime.now()
        self.instance_count = 0

        self.cache: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self.registry: set[Any] = set()

        # Retry state
        self.retry_count = 0

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
                self.logger.debug(f"Loading modifier {entry_point.name}")
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
                self.logger.debug(f"Loading global modifier {entry_point.name}")
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

    def refresh(self) -> bool:
        self.stats.increment("sources.attempt")

        # Get retry config from global source config
        max_retries = config.source_config.max_retries

        try:
            new = SourceData()
            for source in self.sources:
                scope = source.scope
                if scope not in new.scopes:
                    new.scopes[scope] = []
                new.scopes[scope].extend(source.get())
        except Exception as e:
            self.retry_count += 1
            self.logger.error(
                event=f"Error while refreshing sources (attempt {self.retry_count}/{max_retries})",
                traceback=[line for line in traceback.format_exc().split("\n")],
                error=e.__class__.__name__,
                detail=getattr(e, "detail", "-"),
                retry_count=self.retry_count,
            )
            self.stats.increment("sources.error")

            if self.retry_count >= max_retries:
                # Reset retry count for next cycle
                self.retry_count = 0
                self.stats.increment("sources.error.final")
            return False

        # Success - reset retry count
        self.retry_count = 0

        # Is the new data the same as what we currently have
        if new == getattr(self, "source_data", None):
            self.stats.increment("sources.unchanged")
            self.last_updated = datetime.now()
            return False
        else:
            self.stats.increment("sources.refreshed")
            self.last_updated = datetime.now()
            old_data = getattr(self, "source_data", None)
            self.instance_count = len(
                [instance for scope in new.scopes.values() for instance in scope]
            )

            if config.logging.log_source_diffs:
                diff_summary = source_diff_summary(old_data, new)
                # printing json directly because the logger is fucking stupid
                print(
                    json.dumps(
                        dict(
                            event="Sources refreshed with changes",
                            level="info",
                            diff=diff_summary,
                            total_instances=self.instance_count,
                        )
                    )
                )

            self.source_data = new
            return True

    def extract_node_key(self, node: Union[Node, Dict[Any, Any]]) -> Any:
        if self.node_match_key is None:
            return
        if "." not in self.node_match_key:
            # key is not nested, don't need glom
            node_value = getattr(node, self.node_match_key)
        else:
            try:
                node_value = glom(node, self.node_match_key)
            except PathAccessError:
                raise RuntimeError(
                    f'Failed to find key "{self.node_match_key}" in discoveryRequest({node})'
                )
        return node_value

    def extract_source_key(self, source: Dict[Any, Any]) -> Any:
        if self.source_match_key is None:
            return
        if "." not in self.source_match_key:
            # key is not nested, don't need glom
            source_value = source[self.source_match_key]
        else:
            try:
                source_value = glom(source, self.source_match_key)
            except PathAccessError:
                raise RuntimeError(
                    f'Failed to find key "{self.source_match_key}" in instance({source})'
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

        ret = SourceData()
        if modify:
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
                    if scope not in ret.scopes:
                        ret.scopes[scope] = []
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

    def add_to_context(self, request, output):
        """middleware for adding matched instances to context"""
        node_value = self.extract_node_key(request.node)
        self.registry.add(node_value)

        if instances := self.cache.get(node_value, None):
            output.update(instances)
            return

        result = self.get_filtered_instances(node_value)
        output.update(result)

    def get_filtered_instances(self, node_value):
        matches = self.match_node(node_value=node_value)
        result = {}
        for scope, instances in matches.scopes.items():
            if scope in ("default", None):
                result["instances"] = instances
            else:
                result[scope] = instances
        self.cache[node_value] = result
        return result

    def poll(self) -> None:
        updated = self.refresh()
        self.source_data_modified = self.apply_modifications(self.source_data)
        if updated:
            self.cache.clear()
            NEW_CONTEXT.set()

    async def poll_forever(self) -> None:
        while True:
            try:
                self.poll()

                # If we have retry count, use exponential backoff for next attempt
                if self.retry_count > 0:
                    retry_delay = config.source_config.retry_delay
                    delay = min(
                        retry_delay * (2 ** (self.retry_count - 1)),
                        self.source_refresh_rate,  # Cap at normal refresh rate
                    )
                    await asyncio.sleep(delay)
                else:
                    await asyncio.sleep(self.source_refresh_rate)
            except Exception as e:
                self.logger.error(f"Unexpected error in poll loop: {e}")
                await asyncio.sleep(self.source_refresh_rate)
