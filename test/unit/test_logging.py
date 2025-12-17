import json

import structlog
from structlog.testing import CapturingLoggerFactory

from sovereign.configuration import (
    AccessLogConfiguration,
    ApplicationLogConfiguration,
    LoggingConfiguration,
    SovereignConfigv2,
    TemplateConfiguration,
)
from sovereign.logging.bootstrapper import LoggerBootstrapper
from sovereign.logging.types import LoggingType

EMPTY_TEMPLATE_CONF = TemplateConfiguration(default=[])


def test_debug_logs_are_dropped_when_false():
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, debug=False
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf, processors=[logs.debug_logs_processor])

    logs.logger.info("test log info")
    logs.logger.debug("test log debug")

    assert len(cf.logger.calls) == 1


def test_debug_logs_are_dropped_by_default():
    sovereign_config = SovereignConfigv2(sources=[], templates=EMPTY_TEMPLATE_CONF)
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf, processors=[logs.debug_logs_processor])

    logs.logger.info("test log info")
    logs.logger.debug("test log debug")

    assert len(cf.logger.calls) == 1


def test_debug_logs_are_not_dropped_when_true():
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, debug=True
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf, processors=[logs.debug_logs_processor])

    logs.logger.info("test log info")
    logs.logger.debug("test log debug")

    assert len(cf.logger.calls) == 2


def test_access_logs_are_dropped_when_not_enabled():
    access_log_config = AccessLogConfiguration(enabled=False)
    logging_config = LoggingConfiguration(access_logs=access_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.access_logger.logger.info("test log info")
    logs.access_logger.logger.error("test log error")

    assert len(cf.logger.calls) == 0


def test_access_logs_are_not_dropped_when_enabled():
    access_log_config = AccessLogConfiguration(enabled=True)
    logging_config = LoggingConfiguration(access_logs=access_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.access_logger.logger.info("test log info")
    logs.access_logger.logger.error("test log error")

    assert len(cf.logger.calls) == 2


def test_access_logs_entries_contains_dash_when_ignore_empty_fields_false():
    access_log_config = AccessLogConfiguration(enabled=True, ignore_empty_fields=False)
    logging_config = LoggingConfiguration(access_logs=access_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.access_logger.logger.info(event="test log info")
    logs.access_logger.logger.error(event="test log error")

    assert len(cf.logger.calls) == 2
    for call in cf.logger.calls:
        args = call.args[0]
        parsed_args = json.loads(args)
        assert parsed_args["env"] == "-"


def test_access_logs_entries_are_removed_when_ignore_empty_fields_true():
    access_log_config = AccessLogConfiguration(enabled=True, ignore_empty_fields=True)
    logging_config = LoggingConfiguration(access_logs=access_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.access_logger.logger.error(event="test log error")

    assert len(cf.logger.calls) == 1
    input_log_call = cf.logger.calls[0]
    args = input_log_call.args[0]
    parsed_args = json.loads(args)
    assert "env" not in parsed_args


def test_access_logs_can_use_custom_formatter():
    custom_formatter = json.dumps(
        {
            "key1": "{key1}",
            "key2": "{key2}",
            "event": "{event}",
        }
    )
    access_log_config = AccessLogConfiguration(enabled=True, log_fmt=custom_formatter)
    logging_config = LoggingConfiguration(access_logs=access_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.access_logger.logger.info(
        event="test event", key1="value1", key2="value2", key3="value3"
    )

    assert len(cf.logger.calls) == 1
    input_log_call = cf.logger.calls[0]
    args = input_log_call.args[0]
    parsed_args = json.loads(args)
    assert parsed_args.get("event") == "test event"
    assert parsed_args.get("key1") == "value1"
    assert parsed_args.get("key2") == "value2"
    assert "key3" not in parsed_args


def test_access_custom_logs_automatically_add_event_field():
    custom_formatter = json.dumps(
        {
            "key1": "{key1}",
            "key2": "{key2}",
        }
    )
    access_log_config = AccessLogConfiguration(enabled=True, log_fmt=custom_formatter)
    logging_config = LoggingConfiguration(access_logs=access_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.access_logger.logger.info(
        event="test event", key1="value1", key2="value2", key3="value3"
    )

    assert len(cf.logger.calls) == 1
    input_log_call = cf.logger.calls[0]
    args = input_log_call.args[0]
    parsed_args = json.loads(args)
    assert parsed_args.get("event") == "test event"
    assert parsed_args.get("key1") == "value1"
    assert parsed_args.get("key2") == "value2"
    assert "key3" not in parsed_args


def test_application_logs_are_dropped_when_not_enabled():
    application_log_config = ApplicationLogConfiguration(enabled=False)
    logging_config = LoggingConfiguration(application_logs=application_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.application_logger.logger.info("test log info")
    logs.application_logger.logger.error("test log error")

    assert len(cf.logger.calls) == 0


def test_application_logs_are_not_dropped_when_enabled():
    application_log_config = ApplicationLogConfiguration(enabled=True)
    logging_config = LoggingConfiguration(application_logs=application_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.application_logger.logger.info("test log info")
    logs.application_logger.logger.error("test log error")

    assert len(cf.logger.calls) == 2


def test_application_logs_can_use_custom_formatter():
    custom_formatter = json.dumps(
        {
            "key1": "{key1}",
            "key2": "{key2}",
            "event": "{event}",
        }
    )
    application_log_config = ApplicationLogConfiguration(
        enabled=True, log_fmt=custom_formatter
    )
    logging_config = LoggingConfiguration(application_logs=application_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.application_logger.logger.info(
        event="test event", key1="value1", key2="value2", key3="value3"
    )

    assert len(cf.logger.calls) == 1
    input_log_call = cf.logger.calls[0]
    args = input_log_call.args[0]
    parsed_args = json.loads(args)
    assert parsed_args.get("event") == "test event"
    assert parsed_args.get("key1") == "value1"
    assert parsed_args.get("key2") == "value2"
    assert "key3" not in parsed_args


def test_application_custom_logs_automatically_add_event_field():
    custom_formatter = json.dumps(
        {
            "key1": "{key1}",
            "key2": "{key2}",
        }
    )
    application_log_config = ApplicationLogConfiguration(
        enabled=True, log_fmt=custom_formatter
    )
    logging_config = LoggingConfiguration(application_logs=application_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.application_logger.logger.info(
        event="test event", key1="value1", key2="value2", key3="value3"
    )

    assert len(cf.logger.calls) == 1
    input_log_call = cf.logger.calls[0]
    args = input_log_call.args[0]
    parsed_args = json.loads(args)
    assert parsed_args.get("event") == "test event"
    assert parsed_args.get("key1") == "value1"
    assert parsed_args.get("key2") == "value2"
    assert "key3" not in parsed_args


def test_access_and_application_loggers_work_at_same_time():
    access_log_config = AccessLogConfiguration(enabled=True)
    application_log_config = ApplicationLogConfiguration(enabled=True)
    logging_config = LoggingConfiguration(
        access_logs=access_log_config, application_logs=application_log_config
    )
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.access_logger.logger.info("test log info")
    logs.access_logger.logger.error("test log error")
    logs.application_logger.logger.info("test log info")
    logs.application_logger.logger.error("test log error")

    assert len(cf.logger.calls) == 4


def test_access_logs_contain_correct_type_field():
    access_log_config = AccessLogConfiguration(enabled=True)
    logging_config = LoggingConfiguration(access_logs=access_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.access_logger.logger.info(event="test event")

    assert len(cf.logger.calls) == 1
    input_log_call = cf.logger.calls[0]
    args = input_log_call.args[0]
    parsed_args = json.loads(args)
    assert parsed_args.get("type") == LoggingType.ACCESS


def test_application_logs_contain_correct_type_field():
    application_log_config = ApplicationLogConfiguration(enabled=True)
    logging_config = LoggingConfiguration(application_logs=application_log_config)
    sovereign_config = SovereignConfigv2(
        sources=[], templates=EMPTY_TEMPLATE_CONF, logging=logging_config
    )
    logs = LoggerBootstrapper(config=sovereign_config)

    cf = CapturingLoggerFactory()
    structlog.configure(logger_factory=cf)

    logs.application_logger.logger.info(event="test event")

    assert len(cf.logger.calls) == 1
    input_log_call = cf.logger.calls[0]
    args = input_log_call.args[0]
    parsed_args = json.loads(args)
    assert parsed_args.get("type") == LoggingType.APPLICATION
