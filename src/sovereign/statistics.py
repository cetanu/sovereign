# type: ignore
import logging
from typing import Optional, Any, Callable
from functools import wraps
from sovereign import config

try:
    from datadog import DogStatsd

    class CustomStatsd(DogStatsd):
        def _report(self, metric, metric_type, value, tags, sample_rate) -> None:
            super()._report(metric, metric_type, value, tags, sample_rate)
            stats.emitted[metric] = stats.emitted.setdefault(metric, 0) + 1

    statsd = CustomStatsd()
except ImportError:
    if config.statsd.enabled:
        raise
    statsd = None


class StatsDProxy:
    def __init__(self, statsd_instance: Optional[Any] = None) -> None:
        self.statsd = statsd_instance
        self.emitted = dict()

    def __getattr__(self, item: str) -> Any:
        if self.statsd is not None:
            return getattr(self.statsd, item)
        try:
            return StatsdNoop
        except TypeError:
            return self.do_nothing

    def do_nothing(self, *args: Any, **kwargs: Any) -> None:
        k = args[0]
        stats.emitted[k] = stats.emitted.setdefault(k, 0) + 1


class StatsdNoop:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        k = args[0]
        stats.emitted[k] = stats.emitted.setdefault(k, 0) + 1

    def __enter__(self):
        return self

    def __exit__(self, type: str, value: str, traceback: Any) -> None:
        pass

    def __call__(self, func: Callable[..., Any]):
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any):
            return func(*args, **kwargs)

        return wrapped


def configure_statsd(module: Any) -> StatsDProxy:
    if config.statsd.enabled:
        module.host = config.statsd.host
        module.port = config.statsd.port
        module.namespace = config.statsd.namespace
        module.use_ms = config.statsd.use_ms
        for tag, value in config.statsd.tags.items():
            module.constant_tags.extend([f"{tag}:{value}"])
    else:
        module = None
        statsd_logger = logging.getLogger("datadog.dogstatsd")
        statsd_logger.disabled = True
    return StatsDProxy(module)


stats = configure_statsd(module=statsd)
