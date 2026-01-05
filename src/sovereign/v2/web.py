import asyncio
import logging
import os
import threading

from structlog.typing import FilteringBoundLogger

from sovereign import config
from sovereign.types import DiscoveryRequest, DiscoveryResponse
from sovereign.v2.data.repositories import DiscoveryEntryRepository
from sovereign.v2.data.utils import get_data_store, get_queue
from sovereign.v2.logging import get_named_logger
from sovereign.v2.types import DiscoveryEntry, RenderDiscoveryJob


async def wait_for_discovery_response(
    request: DiscoveryRequest,
) -> DiscoveryResponse | None:
    # 1 - check if the entry already exists in the database with a non-empty response
    # 2 - if it does, return it
    # 3 - if it doesn't, enqueue a new job to render it
    # 4 - poll for up to CACHE_READ_TIMEOUT seconds, if we find a response, return it

    request_hash = request.cache_key(config.cache.hash_rules)

    logger: FilteringBoundLogger = get_named_logger(
        f"{__name__}.{wait_for_discovery_response.__qualname__} ({__file__})",
        level=logging.DEBUG,
    ).bind(
        request_hash=request_hash,
        template_resource_type=request.template.resource_type,
        process_id=os.getpid(),
        thread_id=threading.get_ident(),
    )

    logger.debug("Starting lookup for discovery response")

    data_store = get_data_store()
    discovery_entry_repository = DiscoveryEntryRepository(data_store)

    queue = get_queue()

    discovery_entry = discovery_entry_repository.get(request_hash)

    if not discovery_entry:
        logger.debug(
            "No existing discovery entry found, creating new entry and enqueuing job"
        )

        # we need to save this request to the database
        discovery_entry = DiscoveryEntry(
            request_hash=request_hash,
            template=request.template.resource_type,
            request=request,
            response=None,
        )
        discovery_entry_repository.save(discovery_entry)

    if not discovery_entry.response:
        # enqueue a job to render this discovery request (duplicates handled in the worker)
        job = RenderDiscoveryJob(request_hash=request_hash)
        queue.put(job)

    if discovery_entry.response:
        logger.debug("Returning cached response immediately")
        return discovery_entry.response

    # wait for up to CACHE_READ_TIMEOUT seconds for the response to be populated
    logger.debug(
        "Polling for response",
        timeout=config.cache.read_timeout,
        poll_interval=config.cache.poll_interval_secs,
    )

    start_time = asyncio.get_event_loop().time()
    attempts = 0

    while (
        asyncio.get_event_loop().time() - start_time
    ) < config.cache.read_timeout and discovery_entry.response is None:
        attempts += 1
        discovery_entry = discovery_entry_repository.get(request_hash)
        if discovery_entry is None:
            logger.error("No discovery entry found while polling for response")
            return None
        await asyncio.sleep(config.cache.poll_interval_secs)

    elapsed_time = asyncio.get_event_loop().time() - start_time

    if discovery_entry.response:
        logger.debug(
            "Response received after polling",
            attempts=attempts,
            elapsed_time=elapsed_time,
        )
    else:
        logger.error(
            "Timeout waiting for response", attempts=attempts, elapsed_time=elapsed_time
        )

    return discovery_entry.response
