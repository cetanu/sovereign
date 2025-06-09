import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, Body, Request

from sovereign import cache, poller, template_context, discovery
from sovereign.schemas import RegisterClientRequest, DiscoveryRequest

ONDEMAND = asyncio.Queue()
NEW_CONTEXT = asyncio.Event()
executor = ThreadPoolExecutor(max_workers=4)


def render(id: str, req: DiscoveryRequest):
    assert isinstance(req.resource_type, str)
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


async def render_on_event():
    while True:
        await NEW_CONTEXT.wait()
        try:
            for client, request in worker.state.registry.items():
                assert isinstance(request, DiscoveryRequest)
                render(client, request)
        finally:
            NEW_CONTEXT.clear()


async def render_on_demand():
    while True:
        id, request = await ONDEMAND.get()
        await asyncio.get_event_loop().run_in_executor(executor, render, id, request)
        ONDEMAND.task_done()


@asynccontextmanager
async def lifespan(_: FastAPI):
    asyncio.create_task(render_on_event())
    asyncio.create_task(render_on_demand())
    if poller is not None:
        asyncio.create_task(poller.poll_forever())
    asyncio.create_task(template_context.start_refresh_context())
    yield


worker = FastAPI(lifespan=lifespan)
worker.state.registry = dict()


@worker.get("/health")
def health():
    return "OK"


@worker.post("/register")
async def register(
    request: Request,
    registration: RegisterClientRequest = Body(...),
):
    client_id = cache.client_id(registration.request)
    ONDEMAND.put_nowait((client_id, request))
    request.app.state.registry[client_id] = registration.request
    return "Registered", 202


@worker.get("/registered")
def registered(request: Request):
    return request.app.state.registry
