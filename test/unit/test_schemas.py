import pytest
from sovereign.schemas import ContextConfiguration
from pydantic import ValidationError


@pytest.mark.parametrize("input_rate", [1, 5000, 10000])
def test_context_configuration_refresh_rate_valid(input_rate: int) -> None:
    context_configuration = ContextConfiguration(
        context={}, refresh=True, refresh_rate=input_rate
    )

    assert context_configuration.refresh_rate == input_rate


@pytest.mark.parametrize(
    "input_cron_expression",
    [
        "* * * * *",
        "1 * 2 * 3",
        "*/5 * * * *",
    ],
)
def test_context_configuration_refresh_cron_valid(input_cron_expression: str) -> None:
    context_configuration = ContextConfiguration(
        context={}, refresh=True, refresh_cron=input_cron_expression
    )
    assert context_configuration.refresh_cron == input_cron_expression


@pytest.mark.parametrize(
    "input_cron_expression",
    [
        "* * */5 * * * *",
        "0 0 0 */10 *",
        "test",
    ],
)
def test_context_configuration_refresh_cron_raises_on_invalid_expression(
    input_cron_expression: str,
) -> None:
    with pytest.raises(ValidationError):
        ContextConfiguration(
            context={}, refresh=True, refresh_cron=input_cron_expression
        )


def test_context_configuration_sets_default() -> None:
    context_configuration = ContextConfiguration(context={}, refresh=True)
    assert context_configuration.refresh_rate is not None


def test_context_configuration_raises_on_multiple_refresh_methods() -> None:
    with pytest.raises(RuntimeError):
        ContextConfiguration(
            context={}, refresh=True, refresh_rate=5, refresh_cron="* * * * *"
        )
