import time

from sovereign import stats
from sovereign.v2.data.data_store import ComparisonOperator, DataStoreProtocol, DataType
from sovereign.v2.types import Context, DiscoveryEntry, WorkerNode


class ContextRepository:
    def __init__(self, data_store: DataStoreProtocol):
        self.data_store: DataStoreProtocol = data_store

    @stats.timed("repository.context.get_ms")
    def get(self, name: str) -> Context | None:
        return self.data_store.get(DataType.Context, name)

    @stats.timed("v2.repository.context.get_hash_ms")
    def get_hash(self, name: str) -> int | None:
        return self.data_store.get_property(DataType.Context, name, "data_hash")

    def get_refresh_after(self, name: str) -> int | None:
        return self.data_store.get_property(DataType.Context, name, "refresh_after")

    @stats.timed("v2.repository.context.save_ms")
    def save(self, context: Context) -> bool:
        return self.data_store.set(DataType.Context, context.name, context)

    @stats.timed("v2.repository.context.update_refresh_after_ms")
    def update_refresh_after(self, name: str, refresh_after: int) -> bool:
        return self.data_store.set_property(
            DataType.Context, name, "refresh_after", refresh_after
        )


class DiscoveryEntryRepository:
    def __init__(self, data_store: DataStoreProtocol):
        self.data_store = data_store

    @stats.timed("v2.repository.discovery_entry.get_ms")
    def get(self, request_hash: str) -> DiscoveryEntry | None:
        return self.data_store.get(DataType.DiscoveryEntry, request_hash)

    @stats.timed("v2.repository.discovery_entry.find_by_template_ms")
    def find_all_request_hashes_by_template(self, template: str) -> list[str]:
        return self.data_store.find_all_matching_property(
            DataType.DiscoveryEntry,
            "template",
            ComparisonOperator.EqualTo,
            template,
            "request_hash",
        )

    @stats.timed("v2.repository.discovery_entry.save_ms")
    def save(self, entry: DiscoveryEntry) -> bool:
        return self.data_store.set(DataType.DiscoveryEntry, entry.request_hash, entry)


class WorkerNodeRepository:
    def __init__(self, data_store: DataStoreProtocol):
        self.data_store = data_store

    @stats.timed("v2.repository.worker_node.heartbeat_ms")
    def send_heartbeat(self, node_id: str) -> bool:
        now = int(time.time())
        return self.data_store.set(
            DataType.WorkerNode,
            node_id,
            WorkerNode(node_id=node_id, last_heartbeat=now),
        )

    @stats.timed("v2.repository.worker_node.get_leader_ms")
    def get_leader_node_id(self) -> str | None:
        node: WorkerNode | None = self.data_store.min_by_property(
            DataType.WorkerNode, "node_id"
        )
        if node:
            return node.node_id
        return None

    @stats.timed("v2.repository.worker_node.prune_ms")
    def prune_dead_nodes(self) -> bool:
        """
        Remove any nodes that have not sent a heartbeat in the last 10 minutes.
        """
        now = int(time.time())
        return self.data_store.delete_matching(
            DataType.WorkerNode,
            "last_heartbeat",
            ComparisonOperator.LessThanOrEqualTo,
            now - 600,
        )
