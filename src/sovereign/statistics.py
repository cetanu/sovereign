import logging
from typing import Optional, Any, Callable, Dict
from functools import wraps
from sovereign.schemas import StatsdConfig

emitted: Dict[str, Any] = dict()


class StatsDProxy:
    def __init__(self, statsd_instance: Optional[Any] = None) -> None:
        self.statsd = statsd_instance
        self.emitted = emitted

    def __getattr__(self, item: str) -> Any:
        if self.statsd is not None:
            return getattr(self.statsd, item)
        try:
            return StatsdNoop
        except TypeError:
            return self.do_nothing

    def do_nothing(self, *args: Any, **kwargs: Any) -> None:
        k = args[0]
        emitted[k] = emitted.setdefault(k, 0) + 1


class StatsdNoop:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        k = args[0]
        emitted[k] = emitted.setdefault(k, 0) + 1

    def __enter__(self):  # type: ignore
        return self

    def __exit__(self, type: str, value: str, traceback: Any) -> None:
        pass

    def __call__(self, func: Callable[..., Any]):  # type: ignore
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any):  # type: ignore
            return func(*args, **kwargs)

        return wrapped


def configure_statsd(config: StatsdConfig) -> StatsDProxy:
    try:
        from datadog import DogStatsd

        class CustomStatsd(DogStatsd):  # type: ignore
            def _report(self, metric, metric_type, value, tags, sample_rate) -> None:  # type: ignore
                super()._report(metric, metric_type, value, tags, sample_rate)
                self.emitted: Dict[str, Any] = dict()
                self.emitted[metric] = self.emitted.setdefault(metric, 0) + 1

        module: Optional[CustomStatsd]
        module = CustomStatsd()
        if config.enabled:
            module.host = config.host
            module.port = config.port
            module.namespace = config.namespace
            module.use_ms = config.use_ms
            for tag, value in config.tags.items():
                module.constant_tags.extend([f"{tag}:{value}"])
        else:
            statsd_logger = logging.getLogger("datadog.dogstatsd")
            statsd_logger.disabled = True
            module = None
    except ImportError:
        if config.enabled:
            raise
        module = None

    return StatsDProxy(module)
