import structlog
from structlog.exceptions import DropEvent
from structlog.stdlib import BoundLogger

from sovereign.logging.access_logger import AccessLogger
from sovereign.logging.application_logger import ApplicationLogger
from sovereign.logging.types import EventDict, ProcessedMessage
from sovereign.schemas import SovereignConfigv2


class LoggerBootstrapper:
    def __init__(self, config: SovereignConfigv2) -> None:
        self.show_debug: bool = config.debug

        structlog.configure(
            processors=[
                self.debug_logs_processor,
                structlog.processors.JSONRenderer(),
            ]
        )
        root_logger: BoundLogger = structlog.get_logger()
        self.logger = root_logger

        self.access_logger = AccessLogger(root_logger=root_logger, config=config)
        self.application_logger = ApplicationLogger(
            root_logger=root_logger, config=config
        )

    def debug_logs_processor(
        self, logger: BoundLogger, method_name: str, event_dict: EventDict
    ) -> ProcessedMessage:
        if method_name == "debug" and self.show_debug == False:
            raise DropEvent
        return event_dict
