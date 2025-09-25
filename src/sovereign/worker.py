import asyncio
from typing import Optional, final
from multiprocessing import Process, cpu_count
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


ONDEMAND = RenderQueue()
RENDER_SEMAPHORE = asyncio.Semaphore(cpu_count())


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


def render(job: rendering.RenderJob):
    log.debug(f"Spawning render process for {job.id}")
    process = Process(target=rendering.generate, args=[job])
    process.start()
    return process


async def submit_render(job: rendering.RenderJob):
    async with RENDER_SEMAPHORE:
        process = render(job)
        # Wait for the process to complete to ensure semaphore is held
        # until the actual rendering work is done
        await asyncio.get_event_loop().run_in_executor(None, process.join)


async def render_on_event():
    while True:
        # block forever until new context arrives
        await NEW_CONTEXT.wait()
        log.debug("New context detected, re-rendering templates")
        try:
            if registered := cache.clients():
                log.debug("New context detected, re-rendering templates")
                jobs = [
                    rendering.RenderJob(
                        id=client,
                        request=request,
                        context=template_context.get_context(request),
                    )
                    for client, request in registered
                ]
                tasks = [submit_render(job) for job in jobs]
                size = len(tasks)
                stats.increment("template.render_on_event", tags=[f"batch_size:{size}"])
                await asyncio.gather(*tasks)
                log.debug(f"Completed rendering {size} jobs")
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
        await submit_render(job)
        ONDEMAND.task_done()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Template Rendering
    log.debug("Starting rendering loops")
    asyncio.create_task(render_on_event())
    asyncio.create_task(render_on_demand())

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
