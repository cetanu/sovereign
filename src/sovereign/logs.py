import structlog
import threading

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


structlog.configure(
    processors=[
        merge_log_context_in_thread,
        structlog.processors.JSONRenderer()
    ]
)

LOG = structlog.getLogger()
