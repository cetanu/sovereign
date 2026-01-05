import time

import pytest

from sovereign.v2.data.data_store import DataStoreProtocol, DataType, InMemoryDataStore
from sovereign.v2.data.repositories import WorkerNodeRepository
from sovereign.v2.types import WorkerNode


@pytest.fixture(scope="function")
def data_store():
    return InMemoryDataStore()


@pytest.fixture(scope="function")
def worker_node_repository(data_store):
    return WorkerNodeRepository(data_store)


def test_get_leader(
    data_store: DataStoreProtocol, worker_node_repository: WorkerNodeRepository
):
    """
    Leader should be the node with the lowest ID (when sorted lexicographically).
    """

    # add a node that's not the leader
    data_store.set(
        DataType.WorkerNode,
        "ZZZ not leader",
        WorkerNode(node_id="ZZZ not leader", last_heartbeat=int(time.time())),
    )

    # add a node not to be pruned
    data_store.set(
        DataType.WorkerNode,
        "AAA leader",
        WorkerNode(node_id="AAA leader", last_heartbeat=int(time.time())),
    )

    leader_node_id = worker_node_repository.get_leader_node_id()

    assert leader_node_id == "AAA leader"


def test_prune(
    data_store: DataStoreProtocol, worker_node_repository: WorkerNodeRepository
):
    """
    Nodes with heartbeats older than 10 minutes should be pruned. Keeps healthy nodes.
    """

    # add a node to be pruned
    data_store.set(
        DataType.WorkerNode,
        "dead_node_id",
        WorkerNode(
            node_id="dead_node_id",
            last_heartbeat=int(time.time()) - 700,  # 11 minutes ago to force pruning
        ),
    )

    # add a node not to be pruned
    data_store.set(
        DataType.WorkerNode,
        "alive_node_id",
        WorkerNode(
            node_id="alive_node_id",
            last_heartbeat=int(time.time()) - 60,  # 1 minute ago to force keeping
        ),
    )

    worker_node_repository.prune_dead_nodes()

    assert data_store.get(DataType.WorkerNode, "dead_node_id") is None
    assert data_store.get(DataType.WorkerNode, "alive_node_id") is not None
