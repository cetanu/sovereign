import asyncio
from typing import Optional
from multiprocessing import Process
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Body

from sovereign import (
    cache,
    config,
    rendering,
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
ONDEMAND: asyncio.Queue[tuple[ClientId, DiscoveryRequest]] = asyncio.Queue(100)
executor = ThreadPoolExecutor(4)


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


def render(job: rendering.RenderJob):
    log.debug(f"Spawning render process for {job.id}")
    Process(target=rendering.generate, args=[job]).start()


def batch_render(jobs: list[rendering.RenderJob]):
    log.debug("Spawning batch render process for all clients")
    Process(target=rendering.batch_generate, args=[jobs]).start()


async def render_on_event():
    while True:
        # block forever until new context arrives
        await NEW_CONTEXT.wait()
        stats.increment("template.render_on_event")
        log.debug("New context detected, re-rendering templates")
        try:
            if registered := cache.clients():
                log.debug("New context detected, re-rendering templates")
                batch_render(
                    [
                        rendering.RenderJob(
                            id=client,
                            request=request,
                            context=template_context.get_context(request),
                        )
                        for client, request in registered
                    ]
                )
        finally:
            NEW_CONTEXT.clear()


async def render_on_demand():
    while True:
        id, request = await ONDEMAND.get()
        stats.increment("template.render_on_demand")
        log.debug("Received on-demand request to render templates")
        job = rendering.RenderJob(
            id=id, request=request, context=template_context.get_context(request)
        )
        await asyncio.get_event_loop().run_in_executor(executor, render, job)
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
        import threading

        threading.Thread(target=poller_thread, args=[poller], daemon=True).start()
    yield


def poller_thread(poller):
    log.debug("Starting source poller")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poller.poll_forever())


worker = FastAPI(lifespan=lifespan)
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
    registration: RegisterClientRequest = Body(...),
):
    xds = registration.request
    if not cache.registered(xds):
        log.debug(f"Received registration for new client {xds}")
        ONDEMAND.put_nowait(await cache.register(xds))
        stats.increment("client.registration", tags=["status:registered"])
        return "Registering", 202
    else:
        log.debug("Client already registered")
        stats.increment("client.registration", tags=["status:exists"])
        return "Registered", 200
