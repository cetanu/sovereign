from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from freezegun import freeze_time
from pytest_mock import MockerFixture

from sovereign.utils import timer


class RunOnceException(Exception):
    pass


@pytest.fixture
def initial_datetime():
    return datetime(year=2022, month=1, day=1, hour=1, minute=1, second=0)


def test_wait_until_returns_correct_sleep_seconds(initial_datetime: datetime):
    expected_sleep_time = 3600

    with freeze_time(initial_datetime):
        future_datetime = initial_datetime + timedelta(seconds=expected_sleep_time)
        sleep_time_secs = timer.wait_until(future_datetime)

        assert sleep_time_secs == expected_sleep_time


@pytest.mark.asyncio
@pytest.mark.parametrize("input_delay", (0, 1, 10.5, 100))
async def test_poll_forever_calls_function_and_sleeps(
    mocker: MockerFixture, input_delay: int
):
    test_coroutine = AsyncMock()
    asyncio_sleep_mock = AsyncMock(side_effect=RunOnceException)
    mocker.patch("sovereign.utils.timer.asyncio.sleep", side_effect=asyncio_sleep_mock)

    with pytest.raises(RunOnceException):
        await timer.poll_forever(delay=input_delay, coro=test_coroutine)

    test_coroutine.assert_called_once()
    asyncio_sleep_mock.assert_called_once_with(input_delay)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "cron_expression,expected_delay",
    [
        ("* * * * *", 60),
        ("1 * 2 * 3", 82800),
        ("*/5 * * * *", 240),
        ("0 9-17 * * *", 28740),
    ],
)
async def test_poll_forever_cron_sleeps_correctly(
    mocker: MockerFixture,
    cron_expression: str,
    expected_delay: int,
    initial_datetime: datetime,
):
    test_coroutine = AsyncMock()
    asyncio_sleep_mock = AsyncMock(side_effect=RunOnceException)
    mocker.patch("sovereign.utils.timer.asyncio.sleep", side_effect=asyncio_sleep_mock)
    wait_until_spy = mocker.spy(timer, "wait_until")

    with freeze_time(initial_datetime), pytest.raises(RunOnceException):
        await timer.poll_forever_cron(
            cron_expression=cron_expression, coro=test_coroutine
        )

    test_coroutine.assert_called_once()
    asyncio_sleep_mock.assert_called_once()
    assert wait_until_spy.spy_return == expected_delay
