import pytest
from sovereign.schemas import ContextConfiguration
from pydantic import ValidationError


@pytest.mark.parametrize("input_rate", [1, 5000, 10000])
def test_context_configuration_refresh_rate(input_rate: int) -> None:
    context_configuration = ContextConfiguration(
        context={}, refresh=True, refresh_rate=input_rate
    )

    assert context_configuration.refresh_rate == input_rate


@pytest.mark.parametrize(
    "input_cron_expression,expect_success",
    [
        ("* * * * *", True),
        ("1 * 2 * 3", True),
        ("*/5 * * * *", True),
        ("* * */5 * * * *", False),
        ("test", False),
    ],
)
def test_context_configuration_refresh_cron(
    input_cron_expression: str, expect_success: bool
) -> None:
    if expect_success:
        context_configuration = ContextConfiguration(
            context={}, refresh=True, refresh_cron=input_cron_expression
        )
        assert context_configuration.refresh_cron == input_cron_expression
    else:
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
