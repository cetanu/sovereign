import time
import uuid
import requests
from contextvars import ContextVar
from contextlib import nullcontext

from sovereign import config

_trace_id_ctx_var: ContextVar[str] = ContextVar("trace_id", default="")
_span_id_ctx_var: ContextVar[str] = ContextVar("span_id", default="")


def get_trace_id() -> str:
    return _trace_id_ctx_var.get()


def get_span_id() -> str:
    return _span_id_ctx_var.get()


def generate_128bit():
    return str(uuid.uuid4()).replace("-", "")


def generate_64bit():
    return generate_128bit()[:32]


def timestamp():
    return str(time.time()).replace(".", "")


TRACING = config.tracing
if TRACING is not None:
    TRACING_DISABLED = not TRACING.enabled

    class Tracer:
        def gen_id(self):
            if TRACING.trace_id_128bit:
                trace_id = generate_128bit()
            else:
                trace_id = generate_64bit()
            _trace_id_ctx_var.set(trace_id)
            return trace_id

        def __init__(self, span_name):
            if TRACING_DISABLED:
                return
            span_id = get_span_id()
            self.parent_span_id = None
            if span_id != "":
                # We are already inside a trace context
                self.parent_span_id = span_id
            self.trace_id = get_trace_id()
            self.span_id = self.gen_id()
            self.span_name = span_name

        def __enter__(self):
            if TRACING_DISABLED:
                return nullcontext()
            self.trace = {
                "traceId": self.trace_id,
                "id": self.span_id,
                "name": self.span_name,
                "timestamp": time.time(),
                "tags": TRACING.tags,
            }
            if self.parent_span_id:
                self.trace["parent_span_id"] = self.parent_span_id
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            if TRACING_DISABLED:
                return
            self.trace["duration"] = time.time() - self.trace["timestamp"]
            self.submit()

        def submit(self):
            print(f"{self.span_name}: {self.trace['duration']}")
            try:
                url = f"{TRACING.collector}{TRACING.endpoint}"
                requests.post(url, json=self.trace)
            # pylint: disable=broad-except
            except Exception as e:
                print(f"Failed to submit trace: {self.trace}, Error:{e}")
