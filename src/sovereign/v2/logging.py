import logging
import os
from typing import Any, MutableMapping

import structlog
from pydantic import BaseModel

# noinspection PyProtectedMember
from structlog.dev import RichTracebackFormatter
from structlog.typing import FilteringBoundLogger


def get_named_logger(name: str, level: int = logging.INFO) -> FilteringBoundLogger:
    """
    Gets a structured logger with a specific name to allow us to control log levels separately.

    Set LOG_FORMAT=human for pretty-printed, colourful output.
    """

    # noinspection PyUnusedLocal
    def filter_by_level(
        logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
    ) -> MutableMapping[str, Any]:
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warn": logging.WARN,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL,
            "exception": logging.ERROR,
        }
        method_level = level_map.get(method_name, logging.INFO)
        if method_level < level:
            raise structlog.DropEvent
        return event_dict

    # noinspection PyUnusedLocal
    def serialise_pydantic_models(
        logger: FilteringBoundLogger,
        method_name: str,
        event_dict: MutableMapping[str, Any],
    ) -> MutableMapping[str, Any]:
        for key, value in event_dict.items():
            if isinstance(value, BaseModel):
                event_dict[key] = value.model_dump()
        return event_dict

    log_format = os.environ.get("LOG_FORMAT", "json").lower()
    is_human_format = log_format == "human"

    base_processors = [
        filter_by_level,
        structlog.stdlib.add_log_level,
        serialise_pydantic_models,
        structlog.processors.TimeStamper(
            fmt="iso" if not is_human_format else "%Y-%m-%d %H:%M:%S"
        ),
    ]

    if is_human_format:
        # human-readable format with colours
        final_processors = base_processors + [
            structlog.processors.UnicodeDecoder(),
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=RichTracebackFormatter(show_locals=False),
                pad_event=30,
                sort_keys=False,
            ),
        ]
    else:
        # JSON format for production/machine consumption
        current_processors = list(structlog.get_config()["processors"])
        final_processors = base_processors + current_processors

    return structlog.wrap_logger(
        structlog.PrintLogger(),
        final_processors,
        context_class=dict,
    ).bind(logger_name=name)
