import json
import sqlite3
from hashlib import sha256
from pathlib import Path

from cachelib import FileSystemCache
from typing_extensions import final

from sovereign.configuration import config
from sovereign.types import DiscoveryRequest

INIT = """
CREATE TABLE IF NOT EXISTS registered_clients (
    client_id TEXT PRIMARY KEY,
    discovery_request TEXT NOT NULL
)
"""
INSERT = "INSERT OR IGNORE INTO registered_clients (client_id, discovery_request) VALUES (?, ?)"
LIST = "SELECT client_id, discovery_request FROM registered_clients"
SEARCH = "SELECT 1 FROM registered_clients WHERE client_id = ?"


@final
class FilesystemCache:
    def __init__(self, cache_path: str | None = None, default_timeout: int = 0):
        self.cache_path = cache_path or config.cache.local_fs_path
        self.default_timeout = default_timeout  # 0 = infinite TTL

        self._cache = FileSystemCache(
            cache_dir=self.cache_path,
            default_timeout=self.default_timeout,
            hash_method=sha256,
        )

        # Initialize SQLite for client registration
        Path(self.cache_path).mkdir(parents=True, exist_ok=True)
        self._db_path = Path(self.cache_path) / "clients.db"
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
            _ = conn.execute(INIT)

    def get(self, key):
        return self._cache.get(key)

    def set(self, key, value, timeout=None):
        return self._cache.set(key, value, timeout)

    def delete(self, key):
        return self._cache.delete(key)

    def clear(self):
        return self._cache.clear()

    def register(self, id: str, req: DiscoveryRequest) -> None:
        with sqlite3.connect(self._db_path) as conn:
            _ = conn.execute(INSERT, (id, json.dumps(req.model_dump())))

    def registered(self, id: str) -> bool:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(SEARCH, (id,))
            return cursor.fetchone() is not None

    def get_registered_clients(self) -> list[tuple[str, DiscoveryRequest]]:
        with sqlite3.connect(self._db_path) as conn:
            cursor = conn.execute(LIST)
            rows = cursor.fetchall()

        result = []
        for client_id, req_json in rows:
            req = DiscoveryRequest.model_validate(json.loads(req_json))
            result.append((client_id, req))
        return result
