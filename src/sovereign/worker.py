import asyncio
from contextlib import asynccontextmanager
from typing import final

from fastapi import Body, FastAPI

from sovereign import (
    application_logger as log,
)
from sovereign import (
    cache,
    disabled_ciphersuite,
    rendering,
    server_cipher_container,
    stats,
)
from sovereign.configuration import config
from sovereign.context import TemplateContext
from sovereign.events import Topic, bus
from sovereign.types import DiscoveryRequest, RegisterClientRequest


# noinspection PyUnusedLocal
def hidden_field(*args, **kwargs):
    return "(value hidden)"


def inject_builtin_items(request, output):
    output["__hide_from_ui"] = lambda v: v
    output["crypto"] = server_cipher_container
    if request.is_internal_request:
        output["__hide_from_ui"] = hidden_field
        output["crypto"] = disabled_ciphersuite


template_context = TemplateContext.from_config()
context_middleware = [inject_builtin_items]
template_context.middleware = context_middleware
writer = cache.CacheWriter()

ClientId = str
OnDemandJob = tuple[ClientId, DiscoveryRequest]


@final
class RenderQueue:
    def __init__(self, maxsize: int = 0):
        self._queue: asyncio.Queue[OnDemandJob] = asyncio.Queue(maxsize)
        self._set: set[ClientId] = set()
        self._lock = asyncio.Lock()

    async def put(self, item: OnDemandJob):
        cid = item[0]
        async with self._lock:
            if cid not in self._set:
                await self._queue.put(item)
                self._set.add(cid)

    def put_nowait(self, item: OnDemandJob):
        cid = item[0]
        if cid in self._set:
            return
        if self._queue.full():
            raise asyncio.QueueFull
        self._queue.put_nowait(item)
        self._set.add(cid)

    async def get(self):
        return await self._queue.get()

    def full(self):
        return self._queue.full()

    async def task_done(self, cid):
        async with self._lock:
            self._set.remove(cid)
        self._queue.task_done()


ONDEMAND = RenderQueue()


poller = None
if config.sources is not None:
    if config.matching is not None:
        matching_enabled = config.matching.enabled
        node_key: str | None = config.matching.node_key
        source_key: str | None = config.matching.source_key
    else:
        matching_enabled = False
        node_key = None
        source_key = None


async def render_on_event(ctx):
    subscription = bus.subscribe(Topic.CONTEXT)
    while True:
        # block forever until new context arrives
        event = await subscription.get()
        context_name = event.metadata.get("name")

        log.debug(event.message)
        try:
            if registered := writer.get_registered_clients():
                size = len(registered)
                stats.increment("template.render_on_event", tags=[f"batch_size:{size}"])

                for client, request in registered:
                    if context_name in request.template.depends_on:
                        log.info(
                            f"Rendering template on-event for {request} because {context_name} was updated"
                        )
                        job = rendering.RenderJob(
                            id=client,
                            request=request,
                            context=ctx.get_context(request),
                        )
                        job.submit()

        finally:
            await asyncio.sleep(config.template_context.cooldown)


async def render_on_demand(ctx):
    while True:
        cid, request = await ONDEMAND.get()
        stats.increment("template.render_on_demand")
        log.debug(
            f"Received on-demand request to render templates for {cid} ({request})"
        )
        job = rendering.RenderJob(
            id=cid, request=request, context=ctx.get_context(request)
        )
        _ = job.submit()
        await ONDEMAND.task_done(cid)


# noinspection PyProtectedMember
async def monitor_render_queue():
    """Periodically report render queue size metrics"""
    while True:
        await asyncio.sleep(10)
        stats.gauge("template.on_demand_queue_size", ONDEMAND._queue.qsize())


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Template Rendering
    log.debug("Starting rendering loops")
    asyncio.create_task(render_on_event(template_context))
    asyncio.create_task(render_on_demand(template_context))
    asyncio.create_task(monitor_render_queue())

    # Template context
    subscription = bus.subscribe(Topic.CONTEXT)
    log.debug("Starting context loop")
    asyncio.create_task(template_context.start())
    event = await subscription.get()
    log.debug(event.message)

    log.debug("Worker lifespan initialized")
    yield


worker = FastAPI(lifespan=lifespan)
if dsn := config.sentry_dsn.get_secret_value():
    try:
        # noinspection PyUnusedImports
        import sentry_sdk

        # noinspection PyUnusedImports
        from sentry_sdk.integrations.asgi import SentryAsgiMiddleware

        sentry_sdk.init(dsn)
        worker.add_middleware(SentryAsgiMiddleware)  # type: ignore
    except ImportError:  # pragma: no cover
        log.error("Sentry DSN configured but failed to attach to worker")


@worker.get("/health")
def health():
    return "OK"


@worker.put("/client")
async def client_add(
    registration: RegisterClientRequest = Body(...),
):
    log.info(f"Received registration: {registration.request}")
    xds = registration.request
    client_id, req = writer.register(xds)
    ONDEMAND.put_nowait((client_id, req))
    return "Registered", 200
