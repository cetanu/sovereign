import logging
from typing import Optional, Any, Callable, Dict
from functools import wraps
from sovereign.schemas import config as sovereign_config

STATSD: Dict[str, Optional["StatsDProxy"]] = {"instance": None}


class StatsDProxy:
    def __init__(self, statsd_instance: Optional[Any] = None) -> None:
        self.statsd = statsd_instance

    def __getattr__(self, item: str) -> Any:
        if self.statsd is not None:
            return getattr(self.statsd, item)
        try:
            return StatsdNoop
        except TypeError:
            return self.do_nothing

    def do_nothing(self, *args: Any, **kwargs: Any) -> None:
        _ = args[0]


class StatsdNoop:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):  # type: ignore
        return self

    def __exit__(self, type: str, value: str, traceback: Any) -> None:
        pass

    def __call__(self, func: Callable[..., Any]):  # type: ignore
        @wraps(func)
        def wrapped(*args: Any, **kwargs: Any):  # type: ignore
            return func(*args, **kwargs)

        return wrapped


def configure_statsd() -> StatsDProxy:
    if STATSD["instance"] is not None:
        return STATSD["instance"]
    config = sovereign_config.statsd
    try:
        from datadog import DogStatsd

        module: Optional[DogStatsd]
        module = DogStatsd()
        if config.enabled and module:
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

    ret = StatsDProxy(module)
    if STATSD["instance"] is None:
        STATSD["instance"] = ret
    return ret
