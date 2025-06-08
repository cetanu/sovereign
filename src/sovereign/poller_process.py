import asyncio
import os
from typing import Dict

from fastapi import FastAPI
import uvicorn

from sovereign import poller, template_context
from sovereign.constants import POLLER_HOST, POLLER_PORT
from sovereign.views.discovery import perform_discovery, discovery_cache
from sovereign.schemas import DiscoveryRequest, ProcessedTemplate
from sovereign.utils.version_info import compute_hash
from sovereign.utils.timer import poll_forever, poll_forever_cron

app = FastAPI()

# store discovery requests and cached templates
render_cache: Dict[str, ProcessedTemplate] = {}
seen_requests: Dict[str, DiscoveryRequest] = {}


def request_cache_key(
    req: DiscoveryRequest, api_version: str, resource_type: str
) -> str:
    """Compute the cache key for a discovery request."""
    hash_keys = [
        api_version,
        resource_type,
        req.envoy_version,
        req.resources,
        req.desired_controlplane,
        req.hide_private_keys,
        req.type_url,
        req.node.cluster,
        req.node.locality,
        req.node.metadata.get("auth"),
        req.node.metadata.get("num_cpus"),
    ]

    metadata_keys = discovery_cache.extra_keys.get("metadata", [])
    hash_keys += [req.node.metadata.get(key) for key in metadata_keys]

    env_keys = discovery_cache.extra_keys.get("env_vars", [])
    hash_keys += [os.getenv(key) for key in env_keys]

    return compute_hash(*hash_keys)


@app.on_event("startup")
async def start_tasks() -> None:
    app.state.tasks = []
    app.state.render_cache = render_cache
    app.state.seen_requests = seen_requests

    if poller is not None:
        async def poll_loop() -> None:
            previous = compute_hash(repr(poller.source_data))
            while True:
                poller.poll()
                current = compute_hash(repr(poller.source_data))
                if current != previous:
                    render_cache.clear()
                    previous = current
                await asyncio.sleep(poller.source_refresh_rate)

        app.state.tasks.append(asyncio.create_task(poll_loop()))

    async def context_loop() -> None:
        prev_ctx = compute_hash(repr(template_context.context))

        async def refresh() -> None:
            nonlocal prev_ctx
            await template_context.refresh_context()
            current_ctx = compute_hash(repr(template_context.context))
            if current_ctx != prev_ctx:
                render_cache.clear()
                prev_ctx = current_ctx

        if template_context.refresh_cron is not None:
            await poll_forever_cron(template_context.refresh_cron, refresh)
        elif template_context.refresh_rate is not None:
            await poll_forever(template_context.refresh_rate, refresh)
        else:
            raise RuntimeError(
                "Failed to start refresh_context, this should never happen"
            )

    app.state.tasks.append(asyncio.create_task(context_loop()))


@app.on_event("shutdown")
async def stop_tasks() -> None:
    for task in app.state.tasks:
        task.cancel()


@app.post("/discovery/{api_version}/{xds_type}")
async def handle_discovery(
    api_version: str, xds_type: str, req: DiscoveryRequest
) -> dict:
    """Render a discovery response, caching the result by request hash."""
    cache_key = request_cache_key(req, api_version, xds_type)
    seen_requests[cache_key] = req
    if cached := render_cache.get(cache_key):
        response = cached
    else:
        response = await perform_discovery(req, api_version, xds_type, skip_auth=True)
        render_cache[cache_key] = response
    return {"version_info": response.version_info, "resources": response.resources}


def main(port: int = POLLER_PORT) -> None:
    uvicorn.run(app, host=POLLER_HOST, port=port, log_level="warning", access_log=False)


if __name__ == "__main__":
    main()
