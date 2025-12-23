import time
from unittest.mock import MagicMock, patch

import pytest

from sovereign.v2.data.data_store import InMemoryDataStore
from sovereign.v2.data.worker_queue import InMemoryQueue
from sovereign.v2.types import RefreshContextJob
from sovereign.v2.worker import Worker


@pytest.fixture(scope="function")
def data_store() -> InMemoryDataStore:
    return InMemoryDataStore()


@pytest.fixture(scope="function")
def queue() -> InMemoryQueue:
    return InMemoryQueue()


@pytest.fixture(scope="function")
def worker(data_store: InMemoryDataStore, queue: InMemoryQueue) -> Worker:
    return Worker(data_store, "this_node_id", queue)


def test_heartbeat_sent_before_prune(data_store: InMemoryDataStore, worker: Worker):
    """
    Verify that the heartbeat is sent before pruning takes place to avoid self-pruning.
    """
    call_order = []
    original_send_heartbeat = worker.worker_node_repository.send_heartbeat
    original_prune = worker.worker_node_repository.prune_dead_nodes

    def track_send_heartbeat(node_id):
        call_order.append("heartbeat")
        return original_send_heartbeat(node_id)

    def track_prune_dead_nodes():
        call_order.append("prune")
        return original_prune()

    worker.worker_node_repository.send_heartbeat = track_send_heartbeat
    worker.worker_node_repository.prune_dead_nodes = track_prune_dead_nodes
    worker.worker_node_repository.get_leader_node_id = lambda: "node_id"

    with patch("time.sleep", side_effect=[StopIteration]):
        with pytest.raises(StopIteration):
            worker.context_refresh_loop()

    assert call_order == ["heartbeat", "prune"]


def test_non_leader_skips_context_refresh(
    data_store: InMemoryDataStore,
    queue: InMemoryQueue,
    worker: Worker,
):
    """
    Non-leader nodes should skip context processing, send heartbeats, and then sleep.
    """

    # this node is not the leader
    worker.worker_node_repository.get_leader_node_id = lambda: "not_this_node_id"

    with (
        # when we sleep, break the loop so we only loop once
        patch("sovereign.v2.worker.time.sleep", side_effect=_sleep_side_effect),
    ):
        with pytest.raises(StopIteration):
            worker.context_refresh_loop()

    # no context refresh jobs should have been queued
    assert queue.is_empty()


def test_leader_enqueues_context_refresh_job_when_never_refreshed(
    data_store: InMemoryDataStore,
    queue: InMemoryQueue,
    worker: Worker,
):
    """
    Leader nodes should enqueue context refresh jobs when they've never been refreshed before.
    """
    worker.worker_node_repository.get_leader_node_id = lambda: "this_node_id"

    mock_loadable = MagicMock()
    with (
        patch("sovereign.v2.jobs.refresh_context.get_refresh_after", return_value=100),
        patch("sovereign.v2.worker.config") as mock_config,
        patch("sovereign.v2.worker.time.sleep", side_effect=_sleep_side_effect),
    ):
        mock_config.template_context.context.items.return_value = [
            ("test_context", mock_loadable)
        ]

        with pytest.raises(StopIteration):
            worker.context_refresh_loop()

    assert not queue.is_empty()
    job = queue.get()
    assert isinstance(job, RefreshContextJob)
    assert job.context_name == "test_context"


def test_leader_skips_context_not_due_for_refresh(
    data_store: InMemoryDataStore,
    queue: InMemoryQueue,
    worker: Worker,
):
    """
    Leaders should skip enqueuing a refresh job for contexts that haven't reached their refresh time.
    """
    worker.worker_node_repository.get_leader_node_id = lambda: "this_node_id"

    # when we ask the database for the next refresh_after timestamp,
    # return a timestamp in the future so it's not ready for a refresh yet
    worker.context_repository.get_refresh_after = lambda name: int(time.time() + 1000)

    mock_loadable = MagicMock()
    with (
        patch("sovereign.v2.worker.config") as mock_config,
        patch("sovereign.v2.worker.time.sleep", side_effect=_sleep_side_effect),
    ):
        mock_config.template_context.context.items.return_value = [
            ("test_context", mock_loadable)
        ]

        with pytest.raises(StopIteration):
            worker.context_refresh_loop()

    assert queue.is_empty()


def test_leader_skips_context_when_due(
    data_store: InMemoryDataStore,
    queue: InMemoryQueue,
    worker: Worker,
):
    """
    Leaders should skip enqueuing a refresh job for contexts that have reached their refresh time.
    """
    worker.worker_node_repository.get_leader_node_id = lambda: "this_node_id"

    # when we ask the database for the next refresh_after timestamp,
    # return a timestamp in the past to indicate that it's ready for a refresh immediately
    worker.context_repository.get_refresh_after = lambda name: int(time.time() - 100)

    mock_loadable = MagicMock()
    with (
        patch("sovereign.v2.worker.config") as mock_config,
        patch("sovereign.v2.worker.time.sleep", side_effect=_sleep_side_effect),
    ):
        mock_config.template_context.context.items.return_value = [
            ("test_context", mock_loadable)
        ]

        with pytest.raises(StopIteration):
            worker.context_refresh_loop()

    assert not queue.is_empty()
    job = queue.get()
    assert isinstance(job, RefreshContextJob)
    assert job.context_name == "test_context"


def _sleep_side_effect(seconds):
    """
    The PyCharm debugger adds sleeps of 0.1 to synchronise threads. Ignore those.
    """
    if seconds >= 1:
        raise StopIteration
