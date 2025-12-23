import time

from sovereign.v2.data.data_store import ComparisonOperator, DataStoreProtocol, DataType
from sovereign.v2.types import Context, DiscoveryEntry, WorkerNode


class ContextRepository:
    def __init__(self, data_store: DataStoreProtocol):
        self.data_store: DataStoreProtocol = data_store

    def get(self, name: str) -> Context | None:
        return self.data_store.get(DataType.Context, name)

    def get_hash(self, name: str) -> str | None:
        return self.data_store.get_property(DataType.Context, name, "data_hash")

    def get_refresh_after(self, name: str) -> int | None:
        return self.data_store.get_property(DataType.Context, name, "refresh_after")

    def save(self, context: Context) -> bool:
        return self.data_store.set(DataType.Context, context.name, context)

    def update_refresh_after(self, name: str, refresh_after: int) -> bool:
        return self.data_store.set_property(
            DataType.Context, name, "refresh_after", refresh_after
        )


class DiscoveryEntryRepository:
    def __init__(self, data_store: DataStoreProtocol):
        self.data_store = data_store

    def get(self, request_hash: str) -> DiscoveryEntry | None:
        return self.data_store.get(DataType.DiscoveryJob, request_hash)

    def find_all_request_hashes_by_template(self, template: str) -> list[str]:
        return self.data_store.find_all_matching_property(
            DataType.DiscoveryJob,
            "template",
            ComparisonOperator.EqualTo,
            template,
            "request_hash",
        )

    def save(self, job: DiscoveryEntry) -> bool:
        return self.data_store.set(DataType.DiscoveryJob, job.request_hash, job)


class WorkerNodeRepository:
    def __init__(self, data_store: DataStoreProtocol):
        self.data_store = data_store

    def send_heartbeat(self, node_id: str) -> bool:
        now = int(time.time())
        return self.data_store.set(
            DataType.WorkerNode, node_id, WorkerNode(id=node_id, last_heartbeat=now)
        )

    def get_leader_node_id(self) -> str | None:
        node: WorkerNode | None = self.data_store.min_by_property(
            DataType.WorkerNode, "id"
        )
        if node:
            return node.id
        return None

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
