import time
import uuid
import requests
from contextvars import ContextVar

from sovereign import config

_trace_id_ctx_var: ContextVar[str] = ContextVar("trace_id", default="")


def get_trace_id() -> str:
    return _trace_id_ctx_var.get()


def generate_128bit():
    return str(uuid.uuid4()).replace('-', "")

def generate_64bit():
    return generate_128bit()[:32]

def timestamp():
    return str(time.time()).replace(".","")


class Tracer:
    def gen_id(self):
        if config.tracing.trace_id_128bit:
            return generate_128bit
        return generate_64bit

    def __init__(self, span_name, trace_id=None, parent_span_id=None):
        self.trace_id = trace_id
        if trace_id is None:
            self.trace_id = self.gen_id()

        if parent_span_id is not None:
            self.parent_span_id = parent_span_id

        self.span_id = self.gen_id()
        self.span_name = span_name

    def __enter__(self):
        self.trace = {
            "traceId": self.trace_id,
            "id": self.span_id,
            "name": self.span_name,
            "timestamp": time.time(),
            "tags": config.tracing.tags,
        }
        if self.parent_span_id:
            self.trace["parent_span_id"] = self.parent_span_id
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.trace["duration"] = time.time() - self.trace["timestamp"]
        self.submit()

    def submit(self):
        requests.post(f"{config.tracing.collector}{config.tracing.endpoint}", json=self.trace)
