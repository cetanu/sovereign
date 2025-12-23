import logging
from enum import StrEnum
from typing import Any, Protocol

from structlog.typing import FilteringBoundLogger

from sovereign.v2.logging import get_named_logger
from sovereign.v2.types import Context, DiscoveryEntry, WorkerNode


class ComparisonOperator(StrEnum):
    EqualTo = "equal_to"
    LessThanOrEqualTo = "less_than_or_equal_to"


class DataType(StrEnum):
    Context = "context"
    DiscoveryJob = "discovery_request"
    WorkerNode = "worker_node"


class DataStoreProtocol(Protocol):
    def delete_matching(
        self,
        data_type: DataType,
        property_name: str,
        comparison_operator: ComparisonOperator,
        property_value: Any,
    ) -> bool: ...
    def find_all_matching(
        self,
        data_type: DataType,
        property_name: str,
        comparison_operator: ComparisonOperator,
        property_value: Any,
    ) -> list[Any]: ...
    def find_all_matching_property(
        self,
        data_type: DataType,
        match_property_name: str,
        comparison_operator: ComparisonOperator,
        match_property_value: Any,
        property_name: str,
    ) -> list[Any]: ...
    def get(self, data_type: DataType, key: str) -> Any | None: ...
    def get_property(
        self, data_type: DataType, key: str, property_name: str
    ) -> Any | None: ...
    def min_by_property(
        self,
        data_type: DataType,
        property_name: str,
    ) -> Any | None: ...
    def set(self, data_type: DataType, key: str, value: Any) -> bool: ...
    def set_property(
        self, data_type: DataType, key: str, property_name: str, property_value: Any
    ) -> bool: ...


class InMemoryDataStore(DataStoreProtocol):
    def __init__(self):
        self.logger: FilteringBoundLogger = get_named_logger(
            f"{self.__class__.__module__}.{self.__class__.__qualname__}",
            level=logging.DEBUG,
        )

        self.stores: dict[DataType, dict[str, Any]] = {
            DataType.Context: dict[str, Context](),
            DataType.DiscoveryJob: dict[str, DiscoveryEntry](),
            DataType.WorkerNode: dict[str, WorkerNode](),
        }

    @staticmethod
    def _compare(left: Any, operator: ComparisonOperator, right: Any) -> bool:
        if operator == ComparisonOperator.EqualTo:
            return left == right
        elif operator == ComparisonOperator.LessThanOrEqualTo:
            return left <= right
        return False

    def delete_matching(
        self,
        data_type: DataType,
        property_name: str,
        comparison_operator: ComparisonOperator,
        property_value: Any,
    ) -> bool:
        store: dict[str, Any] = self.stores[data_type]
        for key, store_item in store.items():
            if self._compare(
                getattr(store_item, property_name), comparison_operator, property_value
            ):
                self.logger.debug("Deleting item", data_type=data_type, key=key)
                del store[key]
        return True

    def find_all_matching(
        self,
        data_type: DataType,
        property_name: str,
        comparison_operator: ComparisonOperator,
        property_value: Any,
    ) -> list[Any]:
        store: dict[str, Any] = self.stores[data_type]
        return [
            item
            for item in store.values()
            if self._compare(
                getattr(item, property_name), comparison_operator, property_value
            )
        ]

    def find_all_matching_property(
        self,
        data_type: DataType,
        match_property_name: str,
        comparison_operator: ComparisonOperator,
        match_property_value: Any,
        property_name: str,
    ) -> list[Any]:
        return [
            getattr(value, property_name)
            for value in self.find_all_matching(
                data_type,
                match_property_name,
                comparison_operator,
                match_property_value,
            )
        ]

    def get(self, data_type: DataType, key: str) -> Any | None:
        store: dict[str, Any] = self.stores[data_type]
        return store.get(key)

    def get_property(
        self, data_type: DataType, key: str, property_name: str
    ) -> Any | None:
        if value := self.get(data_type, key):
            return getattr(value, property_name)
        return None

    def min_by_property(
        self,
        data_type: DataType,
        property_name: str,
    ) -> Any | None:
        store = self.stores[data_type]
        if not store:
            return None
        return min(store.values(), key=lambda item: getattr(item, property_name))

    def set(self, data_type: DataType, key: str, value: Any) -> bool:
        store: dict[str, Any] = self.stores[data_type]
        store[key] = value
        return True

    def set_property(
        self, data_type: DataType, key: str, property_name: str, property_value: Any
    ) -> bool:
        item = self.get(data_type, key)
        if item is None:
            return False
        setattr(item, property_name, property_value)
        return True
