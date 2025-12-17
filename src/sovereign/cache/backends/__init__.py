"""
Cache backends module

This module provides the protocol definition for cache backends and
the loading mechanism for extensible cache backends via entry points.
"""

from collections.abc import Sequence
from importlib.metadata import EntryPoints
from typing import Any, Protocol, runtime_checkable

from sovereign import application_logger as log
from sovereign.utils.entry_point_loader import EntryPointLoader


@runtime_checkable
class CacheBackend(Protocol):
    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the cache backend with generic configuration

        Args:
            config: Dictionary containing backend-specific configuration
        """
        ...

    def get(self, key: str) -> Any | None:
        """Get a value from the cache

        Args:
            key: The cache key

        Returns:
            The cached value or None if not found
        """
        ...

    def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        """Set a value in the cache

        Args:
            key: The cache key
            value: The value to cache
            timeout: Optional timeout in seconds
        """
        ...


def get_backend() -> CacheBackend | None:
    from sovereign import config

    cache_config = config.cache.remote_backend
    if not cache_config:
        log.info("No remote cache backend configured, using filesystem only")
        return None

    backend_type = cache_config.type

    loader = EntryPointLoader("cache.backends")
    entry_points: EntryPoints | Sequence[Any] = loader.groups.get("cache.backends", [])

    backend = None
    for ep in entry_points:
        if ep.name == backend_type:
            backend = ep.load()
            break

    if not backend:
        raise KeyError(
            (
                f"Cache backend '{backend_type}' not found. "
                f"Available backends: {[ep.name for ep in entry_points]}"
            )
        )

    backend_config = _process_loadable_config(cache_config.config)
    instance = backend(backend_config)

    if not isinstance(instance, CacheBackend):
        raise TypeError(
            (f"Cache backend '{backend_type}' does not implement CacheBackend protocol")
        )

    log.info(f"Successfully initialized cache backend: {backend_type}")
    return instance


def _process_loadable_config(config: dict[str, Any]) -> dict[str, Any]:
    from sovereign.dynamic_config import Loadable

    processed = {}
    for key, value in config.items():
        try:
            if isinstance(value, str):
                loadable = Loadable.from_legacy_fmt(value)
                processed[key] = loadable.load()
            elif isinstance(value, dict):
                loadable = Loadable(**value)
                processed[key] = loadable.load()
            else:
                processed[key] = value
            continue
        except Exception as e:
            log.warning(f"Failed to load value for {key}: {e}")

        if isinstance(value, dict):
            processed[key] = _process_loadable_config(value)
        else:
            processed[key] = value

    return processed
