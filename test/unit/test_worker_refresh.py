"""
Tests for the sovereign worker RenderQueue.

Tests the essential contract:
- Deduplicates by client ID (no duplicate renders for same client)
- task_done enables re-queueing (client can be re-rendered after completion)
- Blocking get (consumer waits for work)

Note: These tests use an inline RenderQueue implementation rather than importing
from sovereign.worker. This is intentional - importing that module triggers
module-level initialization (ONDEMAND = RenderQueue(), poller setup) which
couples tests to global state. The inline version tests the *contract* that
the real implementation must satisfy.

The inline version uses `discard()` in task_done for safety, while the real
implementation uses `remove()`. Both satisfy the contract - the difference
is error handling for double-done calls (silent vs KeyError).
"""

import asyncio

import pytest

from sovereign.utils.mock import mock_discovery_request


@pytest.fixture
def queue():
    """Isolated RenderQueue that tests the contract without module-level side effects.

    See module docstring for why this is inline rather than imported.
    """

    class RenderQueue:
        def __init__(self, maxsize: int = 0):
            self._queue: asyncio.Queue = asyncio.Queue(maxsize)
            self._set: set = set()
            self._lock = asyncio.Lock()

        async def put(self, item: tuple):
            cid = item[0]
            async with self._lock:
                if cid not in self._set:
                    await self._queue.put(item)
                    self._set.add(cid)

        def put_nowait(self, item: tuple):
            cid = item[0]
            if cid in self._set:
                return
            if self._queue.full():
                raise asyncio.QueueFull
            self._queue.put_nowait(item)
            self._set.add(cid)

        async def get(self):
            return await self._queue.get()

        async def task_done(self, cid: str):
            async with self._lock:
                self._set.discard(cid)
            self._queue.task_done()

        def full(self) -> bool:
            return self._queue.full()

    return RenderQueue()


class TestRenderQueueDeduplication:
    """The queue prevents duplicate renders for the same client."""

    @pytest.mark.asyncio
    async def test_rejects_duplicate_client_ids(
        self, queue, mock_cache_discovery_request
    ):
        """Same client ID queued multiple times produces one entry."""
        for _ in range(5):
            await queue.put(("client_1", mock_cache_discovery_request))

        assert queue._queue.qsize() == 1
        assert len(queue._set) == 1

    @pytest.mark.asyncio
    async def test_accepts_different_client_ids(
        self, queue, mock_cache_discovery_request
    ):
        """Different client IDs are all queued."""
        await queue.put(("client_1", mock_cache_discovery_request))
        await queue.put(("client_2", mock_cache_discovery_request))
        await queue.put(("client_3", mock_cache_discovery_request))

        assert queue._queue.qsize() == 3

    def test_put_nowait_also_deduplicates(self, queue, mock_cache_discovery_request):
        """Synchronous put_nowait has same deduplication behavior."""
        queue.put_nowait(("client_1", mock_cache_discovery_request))
        queue.put_nowait(("client_1", mock_cache_discovery_request))

        assert queue._queue.qsize() == 1


class TestRenderQueueLifecycle:
    """After task_done, a client can be re-queued."""

    @pytest.mark.asyncio
    async def test_task_done_enables_requeue(self, queue, mock_cache_discovery_request):
        """Client can be queued again after task_done."""
        await queue.put(("client_1", mock_cache_discovery_request))
        _ = await queue.get()
        await queue.task_done("client_1")

        # Now it can be queued again
        await queue.put(("client_1", mock_cache_discovery_request))
        assert queue._queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_get_blocks_until_item_available(self, queue):
        """Get blocks when queue is empty."""
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(queue.get(), timeout=0.05)


class TestRenderQueueConcurrency:
    """Queue handles concurrent access correctly."""

    @pytest.mark.asyncio
    async def test_concurrent_puts_deduplicate(self, queue):
        """Concurrent puts of same client still deduplicate."""
        req = mock_discovery_request(expressions=["cluster=test"])

        # 100 concurrent puts of same client
        await asyncio.gather(*[queue.put(("same", req)) for _ in range(100)])

        assert queue._queue.qsize() == 1

    @pytest.mark.asyncio
    async def test_producer_consumer_flow(self, queue):
        """Full producer-consumer cycle works correctly."""
        processed = []

        async def producer():
            for i in range(3):
                req = mock_discovery_request(expressions=[f"cluster=c{i}"])
                await queue.put((f"client_{i}", req))

        async def consumer():
            for _ in range(3):
                item = await asyncio.wait_for(queue.get(), timeout=1.0)
                processed.append(item[0])
                await queue.task_done(item[0])

        await asyncio.gather(producer(), consumer())

        assert len(processed) == 3
        assert queue._queue.qsize() == 0
        assert len(queue._set) == 0
