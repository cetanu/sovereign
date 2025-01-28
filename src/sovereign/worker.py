import asyncio
from typing import Optional
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Body, Request

from sovereign import (
    cache,
    config,
    discovery,
    template_context,
    server_cipher_container,
    disabled_ciphersuite,
    application_logger as log,
    stats,
)
from sovereign.sources import SourcePoller
from sovereign.schemas import RegisterClientRequest, DiscoveryRequest
from sovereign.context import NEW_CONTEXT


ClientId = str
ONDEMAND: asyncio.Queue[tuple[ClientId, DiscoveryRequest]] = asyncio.Queue()
CURRENT_JOBS = set()
executor = ThreadPoolExecutor(max_workers=4)


# TODO: do something about this ---------------------------------------
def hidden_field(*args, **kwargs):
    return "(value hidden)"


def inject_builtin_items(request, output):
    output["__hide_from_ui"] = lambda v: v
    output["crypto"] = server_cipher_container
    if request.is_internal_request:
        output["__hide_from_ui"] = hidden_field
        output["crypto"] = disabled_ciphersuite


context_middleware = [inject_builtin_items]
poller = None
if config.sources is not None:
    if config.matching is not None:
        matching_enabled = config.matching.enabled
        node_key: Optional[str] = config.matching.node_key
        source_key: Optional[str] = config.matching.source_key
    else:
        matching_enabled = False
        node_key = None
        source_key = None
    poller = SourcePoller(
        sources=config.sources,
        matching_enabled=matching_enabled,
        node_match_key=node_key,
        source_match_key=source_key,
        source_refresh_rate=config.source_config.refresh_rate,
        logger=log,
        stats=stats,
    )
    context_middleware.append(poller.add_to_context)


if poller is not None:
    poller.lazy_load_modifiers(config.modifiers)
    poller.lazy_load_global_modifiers(config.global_modifiers)

template_context.middleware = context_middleware
# ---------------------------------------------------------------------


def render(id: str, req: DiscoveryRequest):
    assert isinstance(req.resource_type, str)
    tags = [f"type:{req.resource_type}"]

    if id in CURRENT_JOBS:
        # Prevent rendering the same request rapidly
        stats.increment("template.already_rendering", tags=tags)
        return

    CURRENT_JOBS.add(id)
    stats.increment("template.render", tags=tags)
    with stats.timed("template.render_ms", tags=tags):
        response = discovery.response(req, req.resource_type)
        discovery.add_type_urls(req.api_version, req.resource_type, response.resources)
        cache.write(
            id,
            cache.Entry(
                text=response.rendered.decode(),
                len=len(response.resources),
                version=response.version,
            ),
        )
    CURRENT_JOBS.remove(id)


async def render_on_event():
    while True:
        # block forever until new context arrives
        await NEW_CONTEXT.wait()
        stats.increment("template.render_on_event")
        log.debug("New context detected, re-rendering templates")
        try:
            for client, request in worker.state.registry.items():
                assert isinstance(request, DiscoveryRequest)
                render(client, request)
        finally:
            NEW_CONTEXT.clear()


async def render_on_demand():
    while True:
        id, request = await ONDEMAND.get()
        stats.increment("template.render_on_demand")
        log.debug("Received on-demand request to render templates")
        await asyncio.get_event_loop().run_in_executor(executor, render, id, request)
        ONDEMAND.task_done()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Template Rendering
    log.debug("Starting rendering loops")
    asyncio.create_task(render_on_event())
    asyncio.create_task(render_on_demand())

    # Template context
    log.debug("Starting context loop")
    asyncio.create_task(template_context.start())
    await NEW_CONTEXT.wait()  # first refresh finished

    # Source polling
    if poller is not None:
        log.debug("Starting source poller")
        asyncio.create_task(poller.poll_forever())
    yield


worker = FastAPI(lifespan=lifespan)
worker.state.registry = dict()
try:
    import sentry_sdk
    from sentry_sdk.integrations.asgi import SentryAsgiMiddleware
    SENTRY_DSN = config.sentry_dsn.get_secret_value()
    sentry_sdk.init(SENTRY_DSN)
    worker.add_middleware(SentryAsgiMiddleware)
except ImportError:  # pragma: no cover
    pass


@worker.get("/health")
def health():
    return "OK"


@worker.put("/client")
async def client_add(
    request: Request,
    registration: RegisterClientRequest = Body(...),
):
    stats.increment("template.client.registered")
    xds = registration.request
    log.debug(f"Received registration for new client {xds}")
    client_id = cache.client_id(xds)
    ONDEMAND.put_nowait((client_id, xds))
    request.app.state.registry[client_id] = xds
    return "Registered", 202
