import time
import heapq
import zlib
import datetime
import asyncio
import inspect
from enum import Enum
from typing import Any, Callable, Optional, Union

import pydantic
from croniter import croniter

from sovereign.schemas import DiscoveryRequest, config
from sovereign.statistics import configure_statsd
from sovereign.utils.timer import wait_until
from sovereign.dynamic_config import Loadable


stats = configure_statsd()
DEFAULT_RETRY_INTERVAL = config.template_context.refresh_retry_interval_secs
DEFAULT_NUM_RETRIES = config.template_context.refresh_num_retries
NEW_CONTEXT = asyncio.Event()


class ScheduledTask:
    def __init__(self, task: "ContextTask"):
        self.task = task
        self.due = time.monotonic()

    def __lt__(self, other: "ScheduledTask") -> bool:
        return self.due < other.due

    async def run(
        self, output: dict[str, "ContextResult"], tasks: list["ScheduledTask"]
    ):
        await self.task.refresh(output)
        self.due = time.monotonic() + self.task.seconds_til_next_run
        heapq.heappush(tasks, self)

    def __str__(self) -> str:
        return f"ScheduledTask({self.task.name})"


class TemplateContext:
    def __init__(
        self,
        middleware: Optional[list[Callable[[DiscoveryRequest, dict], None]]] = None,
    ) -> None:
        self.tasks: dict[str, ContextTask] = dict()
        self.results: dict[str, ContextResult] = dict()
        self.hashes: dict[str, int] = dict()
        self.scheduled: list[ScheduledTask] = list()
        self.middleware = middleware or list()
        self.running: set[str] = set()
        self.notify_consumers: Optional[asyncio.Task] = None

    @classmethod
    def from_config(cls) -> "TemplateContext":
        ret = TemplateContext()
        for name, spec in config.template_context.context.items():
            ret.register_task_from_loadable(name, spec)
        return ret

    def register_task(self, task: "ContextTask") -> None:
        self.tasks[task.name] = task
        self.scheduled.append(ScheduledTask(task))

    def register_task_from_loadable(self, name: str, loadable: Loadable) -> None:
        self.register_task(ContextTask.from_loadable(name, loadable))

    def update_hash(self, task: "ContextTask"):
        name = task.name
        result = self.results.get(name)
        old = self.hashes.get(name)
        new = hash(result)

        if old != new:
            stats.increment("context.updated", tags=[f"context:{name}"])
            self.hashes[name] = new
            # Debounced event notification to the worker
            if self.notify_consumers:
                # cancel existing and reset timer
                self.notify_consumers.cancel()
            self.notify_consumers = asyncio.create_task(self.publish_event())

    async def publish_event(self):
        try:
            await asyncio.sleep(3.0)
            NEW_CONTEXT.set()
        except asyncio.CancelledError:
            pass

    def get_context(self, req: DiscoveryRequest) -> dict[str, Any]:
        ret = {r.name: r.data for r in self.results.values()}
        for fn in self.middleware:
            fn(req, ret)
        return ret

    def get(self, key: str, default: Any = None) -> Any:
        if result := self.results.get(key):
            return result.data
        return default

    async def _run_task(self, task: "ContextTask"):
        if task.name in self.running:
            return
        self.running.add(task.name)
        try:
            await task.refresh(self.results)
            self.update_hash(task)
        finally:
            self.running.remove(task.name)

    async def run_once(self):
        heapq.heapify(self.scheduled)
        for next_ in self.scheduled:
            await self._run_task(next_.task)

    async def start(self):
        if not self.scheduled:
            # No context jobs configured
            return
        heapq.heapify(self.scheduled)
        while True:
            # Obtain next task
            next_ = heapq.heappop(self.scheduled)
            task = next_.task
            # Wait for due date
            delay = max(0, next_.due - time.monotonic())
            await asyncio.sleep(delay)
            # reschedule immediately (at next due date)
            next_.due = time.monotonic() + task.seconds_til_next_run
            heapq.heappush(self.scheduled, next_)
            # fire and forget, task writes to mutable dict reference
            # no data race because each task writes to its unique key
            asyncio.create_task(self._run_task(task))


class ContextStatus(Enum):
    READY = "ready"
    PENDING = "pending"
    FAILED = "failed"


class ContextResult(pydantic.BaseModel):
    name: str
    data: Any = None
    state: ContextStatus = ContextStatus.PENDING

    def __str__(self) -> str:
        return f"ContextResult({self.name}, {self.state.value})"

    def __hash__(self) -> int:
        data: bytes = repr(self.data).encode()
        return zlib.adler32(data) & 0xFFFFFFFF


class ContextTask(pydantic.BaseModel):
    name: str
    spec: Loadable
    interval: "TaskInterval"
    retry_policy: Optional["TaskRetryPolicy"] = None

    async def refresh(self, output: dict[str, "ContextResult"]) -> None:
        output[self.name] = await self.try_load()

    async def try_load(self) -> "ContextResult":
        attempts_remaining, retry_interval = TaskRetryPolicy.from_task(self)
        data = ""
        state = ContextStatus.PENDING
        while attempts_remaining > 0:
            stats.increment("context.refresh.attempt", tags=[f"context:{self.name}"])
            try:
                load_fn = self.spec.load
                if inspect.iscoroutinefunction(load_fn):
                    data = await load_fn()
                else:
                    data = load_fn()
                stats.increment(
                    "context.refresh.success", tags=[f"context:{self.name}"]
                )
                state = ContextStatus.READY
                break
            except Exception as e:
                data = str(e)
                state = ContextStatus.FAILED
                stats.increment("context.refresh.error", tags=[f"context:{self.name}"])
            attempts_remaining -= 1
            await asyncio.sleep(retry_interval)
        return ContextResult(
            name=self.name,
            data=data,
            state=state,
        )

    @property
    def seconds_til_next_run(self) -> int:
        match self.interval.value:
            case CronInterval(cron=expression):
                cron = croniter(expression)
                next_date = cron.get_next(datetime.datetime)
                return int(wait_until(next_date))
            case SecondsInterval(seconds=seconds):
                return seconds
            case _:
                return 1

    @classmethod
    def from_loadable(cls, name: str, loadable: Loadable) -> "ContextTask":
        interval = loadable.interval
        if interval is None:
            cfg = config.template_context
            if cfg.refresh_rate is not None:
                interval = str(cfg.refresh_rate)
            elif cfg.refresh_cron is not None:
                interval = cfg.refresh_cron
            else:
                interval = "60"
        retry_policy = None
        if policy := loadable.retry_policy:
            retry_policy = TaskRetryPolicy(**policy)

        return ContextTask(
            name=name,
            spec=loadable,
            interval=TaskInterval.from_str(interval),
            retry_policy=retry_policy,
        )

    def __str__(self) -> str:
        return f"ContextTask({self.name}, {self.spec})"

    __repr__ = __str__


class TaskRetryPolicy(pydantic.BaseModel):
    num_retries: int
    interval: int

    @staticmethod
    def from_task(t: "ContextTask") -> tuple[int, int]:
        interval = DEFAULT_RETRY_INTERVAL
        attempts = 1
        if policy := t.spec.retry_policy:
            try:
                retry_policy = TaskRetryPolicy(**policy)
                interval = retry_policy.interval
                attempts += retry_policy.num_retries
            except Exception as e:
                # TODO: warning
                print(f"Failed to parse retry policy of task: {t}. Error: {e}")
        else:
            attempts += DEFAULT_NUM_RETRIES
        return attempts, interval


class TaskInterval(pydantic.BaseModel):
    value: "TaskIntervalKind"

    @classmethod
    def from_str(cls, s: str) -> "TaskInterval":
        if s.isdigit():
            return TaskInterval(value=SecondsInterval(seconds=int(s)))
        if croniter.is_valid(s):
            return TaskInterval(value=CronInterval(cron=s))
        raise ValueError(f"Invalid interval string: {s}")


class CronInterval(pydantic.BaseModel):
    cron: str


class SecondsInterval(pydantic.BaseModel):
    seconds: int


TaskIntervalKind = Union[CronInterval, SecondsInterval]
