import structlog
from structlog.exceptions import DropEvent
import threading
from sovereign import config


# ----- BEGIN thread-local context -----
#
# The following code allows various parts of the application
# to add key:value pairs to a bound logger before being finally
# emitted.
#
# The context is managed per-thread or per-coroutine, which allows
# multiple requests to emit logs, which have been added to incrementally,
# without conflicting with each other.
#
THREADLOCAL = threading.local()


def _ensure_threadlocal():
    THREADLOCAL.context = getattr(THREADLOCAL, 'context', {})


def merge_log_context_in_thread(logger, method_name, event_dict):
    """
    This processor takes a dict from thread-local context,
    merges it, and returns it to structlog so that it can emit a
    log message, complete with context from different parts
    of the application.
    """
    _ensure_threadlocal()
    context = THREADLOCAL.context.copy()
    context.update(event_dict)
    return context


def new_log_context():
    THREADLOCAL.context = {}


def add_log_context(**kwargs):
    _ensure_threadlocal()
    THREADLOCAL.context.update(kwargs)

# ----- END thread-local context -----


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


structlog.configure(
    processors=[
        AccessLogsEnabled(),
        merge_log_context_in_thread,
        structlog.stdlib.add_log_level,
        FilterDebugLogs(),
        structlog.processors.JSONRenderer()
    ]
)

LOG = structlog.getLogger()
