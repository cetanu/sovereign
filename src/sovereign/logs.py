import structlog
import threading

THREADLOCAL = threading.local()


def merge_in_threadlocal(logger, method_name, event_dict):
    """A structlog processor that merges in a thread-local context"""
    _ensure_threadlocal()
    context = THREADLOCAL.context.copy()
    context.update(event_dict)
    return context


def clear_threadlocal():
    """Clear the thread-local context."""
    THREADLOCAL.context = {}


def bind_threadlocal(**kwargs):
    """Put keys and values into the thread-local context."""
    _ensure_threadlocal()
    THREADLOCAL.context.update(kwargs)


def _ensure_threadlocal():
    if not hasattr(THREADLOCAL, 'context'):
        THREADLOCAL.context = {}


structlog.configure(
    processors=[
        merge_in_threadlocal,
        structlog.processors.JSONRenderer()
    ]
)

LOG = structlog.getLogger()
