from sovereign import config
from sovereign.utils.entry_point_loader import EntryPointLoader
from sovereign.v2.data.data_store import DataStoreProtocol
from sovereign.v2.data.worker_queue import QueueProtocol


def get_data_store() -> DataStoreProtocol:
    entry_points = EntryPointLoader("data_stores")
    data_store: DataStoreProtocol | None = None

    for entry_point in entry_points.groups["data_stores"]:
        if entry_point.name == config.worker_v2_data_store_provider:
            data_store = entry_point.load()()
            break

    if data_store is None:
        raise ValueError(
            f"Data store '{config.worker_v2_data_store_provider}' not found in entry points"
        )

    return data_store


def get_queue() -> QueueProtocol:
    entry_points = EntryPointLoader("queues")

    for entry_point in entry_points.groups["queues"]:
        if entry_point.name == config.worker_v2_queue_provider:
            return entry_point.load()()

    raise ValueError(
        f"Queue '{config.worker_v2_queue_provider}' not found in entry points"
    )
