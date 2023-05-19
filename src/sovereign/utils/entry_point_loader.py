from typing import Dict
from functools import cached_property
from importlib.metadata import entry_points, EntryPoints


class EntryPointLoader:
    ENTRY_POINTS = entry_points()

    def __init__(self, *args: str) -> None:
        self._groups = args

    @classmethod
    def _select(cls, group: str) -> EntryPoints:
        return cls.ENTRY_POINTS.select(group=f"sovereign.{group}")

    @cached_property
    def groups(self) -> Dict[str, EntryPoints]:
        return {group: self._select(group) for group in self._groups}
