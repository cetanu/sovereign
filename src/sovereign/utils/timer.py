import asyncio
import datetime as dt
from datetime import datetime
from typing import Any, Callable, Coroutine, NoReturn

from croniter import croniter


def wait_until(dt: datetime) -> float:
    now = datetime.now()
    sleep_time = (dt - now).total_seconds()
    return sleep_time


async def poll_forever(
    delay: int, coro: Callable[[], Coroutine[Any, Any, Any]]
) -> NoReturn:
    while True:
        await coro()
        await asyncio.sleep(delay)


async def poll_forever_cron(
    cron_expression: str, coro: Callable[[], Coroutine[Any, Any, Any]]
) -> NoReturn:
    croniter_iter = croniter(cron_expression)
    while True:
        await coro()
        next_datetime = croniter_iter.get_next(dt.datetime)
        delay = wait_until(next_datetime)
        await asyncio.sleep(delay)
