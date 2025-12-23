import logging
from typing import Any, MutableMapping

import structlog
from pydantic import BaseModel
from structlog.typing import FilteringBoundLogger


def get_named_logger(name: str, level: int = logging.INFO) -> FilteringBoundLogger:
    """
    Gets a structured logger with a speciifc name to allow us to control log levels separately.
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

    current_processors = list(structlog.get_config()["processors"])

    return structlog.wrap_logger(
        structlog.PrintLogger(),
        processors=[
            filter_by_level,
            structlog.stdlib.add_log_level,
            serialise_pydantic_models,
            structlog.processors.format_exc_info,
        ]
        + current_processors,
        context_class=dict,
    ).bind(logger_name=name)
