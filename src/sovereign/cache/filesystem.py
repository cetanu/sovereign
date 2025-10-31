from hashlib import sha256
from cachelib import FileSystemCache

from sovereign import config
from sovereign.schemas import DiscoveryRequest


class FilesystemCache:
    def __init__(self, cache_path: str | None = None, default_timeout: int = 0):
        self.cache_path = cache_path or config.cache.local_fs_path
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

    def register(self, id: str, req: DiscoveryRequest) -> None:
        clients = self.get_registered_clients()
        if (id, req) in clients:
            return
        clients.append((id, req))
        _ = self._cache.set("_registered_clients", clients)

    def registered(self, id: str) -> bool:
        clients = self.get_registered_clients()
        return any(cid == id for cid, _ in clients)

    def get_registered_clients(self) -> list[tuple[str, DiscoveryRequest]]:
        return self._cache.get("_registered_clients") or []
