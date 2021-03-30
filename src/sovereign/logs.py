import structlog
from structlog.exceptions import DropEvent
from structlog.threadlocal import (
    bind_threadlocal,
    clear_threadlocal,
    merge_threadlocal,
)
from sovereign import config


class AccessLogsEnabled:
    def __call__(self, logger, method_name, event_dict):
        if not config.enable_access_logs:
            raise DropEvent
        return event_dict


class FilterDebugLogs:
    def __call__(self, logger, method_name, event_dict):
        if event_dict.get('level') == 'debug' and not config.debug_enabled:
            raise DropEvent
        return event_dict


def submit_log(*args, **kwargs):
    _logger.msg(*args, **kwargs)
    clear_threadlocal()


structlog.configure(
    processors=[
        AccessLogsEnabled(),
        merge_threadlocal,
        structlog.stdlib.add_log_level,
        FilterDebugLogs(),
        structlog.processors.JSONRenderer()
    ]
)

new_log_context = clear_threadlocal
add_log_context = bind_threadlocal
_logger = structlog.getLogger()

