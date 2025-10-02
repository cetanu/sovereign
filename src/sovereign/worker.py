import asyncio
from typing import Optional, final
from contextlib import asynccontextmanager

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
OnDemandJob = tuple[ClientId, DiscoveryRequest]


@final
class RenderQueue:
    def __init__(self, maxsize: int = 0):
        self._queue: asyncio.Queue[OnDemandJob] = asyncio.Queue(maxsize)
        self._set: set[ClientId] = set()
        self._lock = asyncio.Lock()

    async def put(self, item: OnDemandJob):
        id_ = item[0]
        async with self._lock:
            if id_ not in self._set:
                await self._queue.put(item)
                self._set.add(id_)

    def put_nowait(self, item: OnDemandJob):
        id_ = item[0]
        if id_ in self._set:
            return
        if self._queue.full():
            raise asyncio.QueueFull
        self._queue.put_nowait(item)
        self._set.add(id_)

    async def get(self):
        item = await self._queue.get()
        async with self._lock:
            self._set.remove(item[0])
        return item

    def full(self):
        return self._queue.full()

    def task_done(self):
        self._queue.task_done()


ONDEMAND = RenderQueue()


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


async def render_on_event():
    while True:
        # block forever until new context arrives
        _ = await NEW_CONTEXT.wait()
        log.debug("New context detected, re-rendering templates")
        try:
            if registered := cache.clients():
                log.debug("New context detected, re-rendering templates")
                size = len(registered)
                stats.increment("template.render_on_event", tags=[f"batch_size:{size}"])
                for client, request in registered:
                    job = rendering.RenderJob(
                        id=client,
                        request=request,
                        context=template_context.get_context(request),
                    )
                    job.spawn()
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
        job.spawn()
        ONDEMAND.task_done()


async def monitor_render_queue():
    """Periodically report render queue size metrics"""
    while True:
        await asyncio.sleep(10)
        stats.gauge("template.on_demand_queue_size", ONDEMAND._queue.qsize())


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Template Rendering
    log.debug("Starting rendering loops")
    asyncio.create_task(render_on_event())
    asyncio.create_task(render_on_demand())
    asyncio.create_task(monitor_render_queue())

    # Template context
    log.debug("Starting context loop")
    template_context.middleware = context_middleware
    asyncio.create_task(template_context.start())
    await NEW_CONTEXT.wait()  # first refresh finished

    # Source polling
    if poller is not None:
        log.debug("Starting source poller")
        poller.lazy_load_modifiers(config.modifiers)
        poller.lazy_load_global_modifiers(config.global_modifiers)
        asyncio.create_task(poller.poll_forever())
    yield


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
    if cache.registered(xds):
        log.debug("Client already registered")
        stats.increment("client.registration", tags=["status:exists"])
        return "Registered", 200
    else:
        log.debug(f"Received registration for new client {xds}")
        id, req = await cache.register(xds)
        try:
            ONDEMAND.put_nowait((id, req))
        except asyncio.QueueFull:
            stats.increment("client.registration", tags=["status:queue_full"])
            return "Slow down :(", 429
        stats.increment("client.registration", tags=["status:registered"])
        return "Registering", 202
