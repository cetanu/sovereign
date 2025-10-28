from hashlib import sha256
from cachelib import FileSystemCache

from sovereign import config


class FilesystemCache:
    def __init__(self, cache_path: str | None = None, default_timeout: int = 0):
        self.cache_path = cache_path or config.cache_path
        self.default_timeout = default_timeout
        self._cache = FileSystemCache(
            cache_dir=self.cache_path,
            default_timeout=self.default_timeout,
            hash_method=sha256,
        )

    def get(self, key):
        return self._cache.get(key)

    def set(self, key, value, timeout=None):
        return self._cache.set(key, value, timeout)

    def delete(self, key):
        return self._cache.delete(key)

    def clear(self):
        return self._cache.clear()
