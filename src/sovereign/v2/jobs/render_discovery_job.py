import logging
import os
import threading
import time

from structlog.typing import FilteringBoundLogger

from sovereign import config, disabled_ciphersuite, server_cipher_container, stats
from sovereign.rendering_common import (
    add_type_urls,
    deserialize_config,
    filter_resources,
)
from sovereign.types import DiscoveryResponse, ProcessedTemplate
from sovereign.utils import templates
from sovereign.v2.data.repositories import ContextRepository, DiscoveryEntryRepository
from sovereign.v2.logging import get_named_logger
from sovereign.v2.types import Context, DiscoveryEntry


# noinspection DuplicatedCode
def render_discovery_response(
    request_hash: str,
    context_repository: ContextRepository,
    discovery_entry_repository: DiscoveryEntryRepository,
    node_id: str,
):
    logger: FilteringBoundLogger = get_named_logger(
        f"{__name__}.{render_discovery_response.__qualname__} ({__file__})",
        level=logging.DEBUG,
    ).bind(
        request_hash=request_hash,
        node_id=node_id,
        process_id=os.getpid(),
        thread_id=threading.get_ident(),
    )

    try:
        logger.debug("Starting rendering of discovery response")

        discovery_entry = discovery_entry_repository.get(request_hash)

        if discovery_entry is None:
            logger.error("No discovery entry found for request hash")
            return True  # don't retry this job, it won't succeed

        request = discovery_entry.request

        with stats.timed(
            "v2.worker.job.render_discovery_response_ms",
            template=discovery_entry.request.template.resource_type,
        ):
            logger = logger.bind(
                template=discovery_entry.request.template.resource_type
            )

            dependencies = request.template.depends_on
            contexts: dict[str, Context | None] = {
                name: context_repository.get(name) for name in dependencies
            }

            missing_contexts = [
                name
                for name, context in contexts.items()
                if context is None or context.last_refreshed_at is None
            ]
            if missing_contexts:
                logger.error(
                    "Cannot render template for request, required contexts not yet loaded",
                    missing_contexts=missing_contexts,
                )
                return False

            # in order to handle duplicate jobs for the same request_hash, check the last_rendered_at property - if this is
            # greater than the all the last_refreshed_at values for the contexts, then we can skip rendering
            refresh_times = [
                context.last_refreshed_at
                for context in contexts.values()
                if context is not None and context.last_refreshed_at is not None
            ]

            if refresh_times:
                latest_context_refresh = max(refresh_times)

                if (
                    discovery_entry.last_rendered_at
                    and latest_context_refresh < discovery_entry.last_rendered_at
                ):
                    # the template was last rendered after all the contexts were refreshed, so we can skip rendering
                    logger.info("Skipping rendering for duplicate job")
                    return True

            raw_contexts = {
                name: context.data
                for (name, context) in contexts.items()
                if context is not None
            }

            logger.debug(
                "Contexts loaded for rendering discovery response",
                contexts=raw_contexts.keys(),
                depends_on=request.template.depends_on,
            )

            if request.is_internal_request:
                raw_contexts["__hide_from_ui"] = lambda v: "(value hidden)"
                raw_contexts["crypto"] = disabled_ciphersuite
            else:
                raw_contexts["__hide_from_ui"] = lambda v: v
                raw_contexts["crypto"] = server_cipher_container

            raw_contexts["config"] = config

            result = request.template.generate(
                discovery_request=request,
                host_header=request.desired_controlplane,
                resource_names=request.resources,
                utils=templates,
                **raw_contexts,
            )

            if not request.template.is_python_source:
                assert isinstance(result, str)
                result = deserialize_config(result)

            assert isinstance(result, dict)
            resources = filter_resources(result["resources"], request.resources)
            add_type_urls(request.api_version, request.resource_type, resources)
            processed_template = ProcessedTemplate(resources=resources)
            response = DiscoveryResponse(
                resources=resources, version_info=processed_template.version_info
            )

            if not discovery_entry_repository.save(
                DiscoveryEntry(
                    request_hash=request_hash,
                    template=request.template.resource_type,
                    request=request,
                    response=response,
                    last_rendered_at=int(time.time()),
                )
            ):
                logger.error("Failed to save discovery entry")
    finally:
        logger.debug("Finished rendering of discovery response")
