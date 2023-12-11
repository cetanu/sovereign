import asyncio
import pytest

from sovereign.context import TemplateContext
from unittest.mock import Mock
from sovereign.config_loader import Loadable, Serialization, Protocol


def test_init_context() -> None:
    configured_context = {
        "foo": Loadable(
            protocol=Protocol.inline,
            serialization=Serialization.raw,
            path="bar",
        ),
    }

    context = TemplateContext(
        refresh_rate=None,
        refresh_cron=None,
        refresh_num_retries=3,
        refresh_retry_interval_secs=0,
        configured_context=configured_context,
        poller=Mock(),
        encryption_suite=None,
        disabled_suite=Mock(),
        logger=Mock(),
        stats=Mock(),
    )

    assert context.context["foo"] == "bar"


def test_emit_metric_when_successfully_init_context() -> None:
    mock_stats = Mock()
    mock_stats.increment = Mock()
    configured_context = {
        "foo": Loadable(
            protocol=Protocol.inline,
            serialization=Serialization.raw,
            path="bar",
        ),
    }

    TemplateContext(
        refresh_rate=None,
        refresh_cron=None,
        refresh_num_retries=3,
        refresh_retry_interval_secs=0,
        configured_context=configured_context,
        poller=Mock(),
        encryption_suite=None,
        disabled_suite=Mock(),
        logger=Mock(),
        stats=mock_stats,
    )

    assert mock_stats.increment.call_count == 1
    mock_stats.increment.assert_called_with(
        "context.refresh.success", tags=["context:foo"]
    )


def test_emit_metric_when_failed_to_init_context() -> None:
    mock_stats = Mock()
    mock_stats.increment = Mock()
    configured_context = {
        "foo": Loadable(
            protocol=Protocol.file,
            serialization=Serialization.json,
            path="bad_path",
        ),
    }

    TemplateContext(
        refresh_rate=None,
        refresh_cron=None,
        refresh_num_retries=3,
        refresh_retry_interval_secs=0,
        configured_context=configured_context,
        poller=Mock(),
        encryption_suite=None,
        disabled_suite=Mock(),
        logger=Mock(),
        stats=mock_stats,
    )

    assert mock_stats.increment.call_count == 1
    mock_stats.increment.assert_called_with(
        "context.refresh.error", tags=["context:foo"]
    )


@pytest.mark.parametrize("refresh_num_retries", [0, 1, 5, 999])
def test_context_retries_on_error_before_emitting_metric(refresh_num_retries):
    mock_stats = Mock()
    mock_stats.increment = Mock()
    loadable_mock = Mock(spec_set=Loadable)
    loadable_mock.load = Mock(side_effect=RuntimeError())

    configured_context = {
        "foo": loadable_mock,
    }

    template_context = TemplateContext(
        refresh_rate=None,
        refresh_cron=None,
        refresh_num_retries=refresh_num_retries,
        refresh_retry_interval_secs=0,
        configured_context=configured_context,  # type: ignore
        poller=Mock(),
        encryption_suite=None,
        disabled_suite=Mock(),
        logger=Mock(),
        stats=mock_stats,
    )

    assert template_context.context == {"foo": {}}
    assert (
        loadable_mock.load.call_count == refresh_num_retries + 1
    )  # 1 original + number of retries
    assert mock_stats.increment.call_count == 1


def test_existing_context_remains_unchanged_when_failed_to_load() -> None:
    mockLoadable1 = Mock(spec_set=Loadable)
    mockLoadable1.load = Mock(side_effect=["context 1 value", Exception()])

    mockLoadable2 = Mock(spec_set=Loadable)
    mockLoadable2.load = Mock(side_effect=["context 2 value", "context 2 value - updated"])

    configured_context = {
        "context1": mockLoadable1,
        "context2": mockLoadable2,
    }

    template_context = TemplateContext(
        refresh_rate=None,
        refresh_cron=None,
        refresh_num_retries=1,
        refresh_retry_interval_secs=0,
        configured_context=configured_context,
        poller=Mock(),
        encryption_suite=None,
        disabled_suite=Mock(),
        logger=Mock(),
        stats=Mock(),
    )

    assert len(template_context.context) == 2
    assert template_context.context["context1"] == "context 1 value"
    assert template_context.context["context2"] == "context 2 value"

    asyncio.run(template_context.refresh_context())

    assert len(template_context.context) == 2
    assert template_context.context["context1"] == "context 1 value"
    assert template_context.context["context2"] == "context 2 value - updated"

    
