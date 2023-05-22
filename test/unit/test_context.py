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
        configured_context=configured_context,
        poller=None,
        encryption_suite=None,
        disabled_suite=None,
        logger=None,
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
        configured_context=configured_context,
        poller=None,
        encryption_suite=None,
        disabled_suite=None,
        logger=None,
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
        configured_context=configured_context,
        poller=None,
        encryption_suite=None,
        disabled_suite=None,
        logger=Mock(),
        stats=mock_stats,
    )

    assert mock_stats.increment.call_count == 1
    mock_stats.increment.assert_called_with(
        "context.refresh.error", tags=["context:foo"]
    )
