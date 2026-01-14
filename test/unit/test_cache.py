"""
Tests for the sovereign caching system.

Tests the essential contracts:
- FilesystemCache: get/set and client registration
- S3Backend: get/set with pickling
- CacheReader: local-first with remote fallback and write-back
- CacheWriter: dual-write to local and remote
- client_id: deterministic hashing
"""

import sqlite3
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sovereign.cache.types import Entry
from sovereign.types import Node
from sovereign.utils.mock import mock_discovery_request


class TestFilesystemCache:
    """Tests for FilesystemCache - local cache with SQLite registration."""

    def test_get_set_roundtrip(self, temp_cache_dir, mock_cache_entry):
        """Test basic cache storage and retrieval."""
        from sovereign.cache.filesystem import FilesystemCache

        cache = FilesystemCache(cache_path=temp_cache_dir)

        assert cache.get("key") is None
        cache.set("key", mock_cache_entry)
        result = cache.get("key")

        assert result.text == mock_cache_entry.text
        assert result.version == mock_cache_entry.version

    def test_client_registration_persists(
        self, temp_cache_dir, mock_cache_discovery_request
    ):
        """Test client registration uses SQLite for persistence."""
        from sovereign.cache.filesystem import FilesystemCache

        cache = FilesystemCache(cache_path=temp_cache_dir)
        cache.register("client_1", mock_cache_discovery_request)

        # Verify via SQLite directly
        db_path = Path(temp_cache_dir) / "clients.db"
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute(
                "SELECT client_id FROM registered_clients WHERE client_id = ?",
                ("client_1",),
            )
            assert cursor.fetchone() is not None

        # Verify via API
        assert cache.registered("client_1") is True
        assert cache.registered("unknown") is False

        clients = cache.get_registered_clients()
        assert len(clients) == 1
        assert clients[0][0] == "client_1"

    def test_registration_is_idempotent(
        self, temp_cache_dir, mock_cache_discovery_request
    ):
        """Registering same client multiple times produces one entry."""
        from sovereign.cache.filesystem import FilesystemCache

        cache = FilesystemCache(cache_path=temp_cache_dir)

        for _ in range(3):
            cache.register("client_1", mock_cache_discovery_request)

        assert len(cache.get_registered_clients()) == 1


class TestS3Backend:
    """Tests for S3Backend - remote cache with pickle serialization."""

    def test_get_set_roundtrip(self, mock_s3_bucket, mock_cache_entry):
        """Test S3 storage with pickle serialization."""
        from sovereign.cache.backends.s3 import S3Backend

        backend = S3Backend(
            {
                "bucket_name": mock_s3_bucket["bucket_name"],
                "prefix": mock_s3_bucket["prefix"],
            }
        )

        assert backend.get("key") is None
        backend.set("key", mock_cache_entry)
        result = backend.get("key")

        assert result.text == mock_cache_entry.text
        assert result.node.cluster == mock_cache_entry.node.cluster

    def test_requires_bucket_name(self, mock_s3_bucket):
        """Test initialization fails without bucket_name."""
        from sovereign.cache.backends.s3 import S3Backend

        with pytest.raises(ValueError, match="bucket_name is required"):
            S3Backend({"prefix": "test"})


class TestCacheReader:
    """Tests for CacheReader - the read-through cache logic."""

    def test_local_hit_does_not_trigger_worker_registration(
        self,
        temp_cache_dir,
        mock_s3_bucket,
        mock_cache_entry,
        mock_cache_discovery_request,
    ):
        """Local cache hit returns immediately - no worker registration needed.

        This is the counterpart to test_remote_hit_triggers_worker_registration.
        Local hits are already fresh (rendered by this instance), so no need
        to trigger a re-render via the worker.
        """
        with patch("sovereign.cache.config") as cfg:
            cfg.cache.local_fs_path = temp_cache_dir
            cfg.cache.remote_backend = None
            cfg.cache.hash_rules = ["node.cluster"]

            from sovereign.cache import CacheReader, client_id
            from sovereign.cache.backends.s3 import S3Backend
            from sovereign.cache.filesystem import FilesystemCache

            local = FilesystemCache(cache_path=temp_cache_dir)
            remote = S3Backend(
                {
                    "bucket_name": mock_s3_bucket["bucket_name"],
                    "prefix": mock_s3_bucket["prefix"],
                }
            )

            cid = client_id(mock_cache_discovery_request)
            local.set(cid, mock_cache_entry)

            reader = CacheReader()
            reader.local = local
            reader.remote = remote
            reader.register_async = MagicMock()

            reader.get(mock_cache_discovery_request)

            reader.register_async.assert_not_called()

    def test_falls_back_to_remote_on_local_miss(
        self, temp_cache_dir, mock_s3_bucket, mock_cache_entry
    ):
        """Remote cache is checked when local misses."""
        with patch("sovereign.cache.config") as cfg:
            cfg.cache.local_fs_path = temp_cache_dir
            cfg.cache.remote_backend = None
            cfg.cache.hash_rules = ["node.cluster"]

            from sovereign.cache import CacheReader
            from sovereign.cache.backends.s3 import S3Backend
            from sovereign.cache.filesystem import FilesystemCache

            local = FilesystemCache(cache_path=temp_cache_dir)
            remote = S3Backend(
                {
                    "bucket_name": mock_s3_bucket["bucket_name"],
                    "prefix": mock_s3_bucket["prefix"],
                }
            )

            remote.set("key", mock_cache_entry)

            reader = CacheReader()
            reader.local = local
            reader.remote = remote

            result = reader.try_read("key")

            assert result.from_remote is True
            assert result.value.text == mock_cache_entry.text

    def test_remote_hit_triggers_worker_registration_to_prevent_stuck_cache(
        self,
        temp_cache_dir,
        mock_s3_bucket,
        mock_cache_entry,
        mock_cache_discovery_request,
    ):
        """Reading from S3 triggers async worker registration to prevent stuck cache.

        Fix for commit 36f42fc: When a new instance reads from S3, it must trigger
        a render job via the worker. Without this, the S3 entry gets written to
        local cache and served indefinitely - even if the config becomes stale -
        because no render is triggered until context changes.

        The fix calls _register_and_upgrade_ttl() which:
        1. Writes to local cache immediately with provisional_ttl
        2. Sends HTTP PUT to worker's /client endpoint in background
        3. Upgrades TTL to local_ttl on successful registration
        """
        with patch("sovereign.cache.config") as cfg:
            cfg.cache.local_fs_path = temp_cache_dir
            cfg.cache.remote_backend = None
            cfg.cache.hash_rules = ["node.cluster"]
            cfg.cache.local_ttl = 3600
            cfg.cache.provisional_ttl = 300

            from sovereign.cache import CacheReader, client_id
            from sovereign.cache.backends.s3 import S3Backend
            from sovereign.cache.filesystem import FilesystemCache

            local = FilesystemCache(cache_path=temp_cache_dir)
            remote = S3Backend(
                {
                    "bucket_name": mock_s3_bucket["bucket_name"],
                    "prefix": mock_s3_bucket["prefix"],
                }
            )

            cid = client_id(mock_cache_discovery_request)
            remote.set(cid, mock_cache_entry)

            reader = CacheReader()
            reader.local = local
            reader.remote = remote
            reader._register_and_upgrade_ttl = MagicMock()

            assert local.get(cid) is None  # Empty before

            reader.get(mock_cache_discovery_request)

            assert (
                local.get(cid) is not None
            )  # Written back to local with provisional_ttl
            reader._register_and_upgrade_ttl.assert_called_once()

    def test_register_and_upgrade_ttl_calls_worker_over_http(
        self,
        temp_cache_dir,
        mock_s3_bucket,
        mock_cache_entry,
        mock_cache_discovery_request,
    ):
        """_register_and_upgrade_ttl sends HTTP request to worker and upgrades TTL on success.

        This is the mechanism that prevents stuck cache - the worker receives
        the registration and queues an on-demand render job. On success, the
        cache entry's TTL is upgraded from provisional_ttl to local_ttl.
        """
        with patch("sovereign.cache.config") as cfg:
            cfg.cache.local_fs_path = temp_cache_dir
            cfg.cache.remote_backend = None
            cfg.cache.hash_rules = ["node.cluster"]
            cfg.cache.local_ttl = 3600
            cfg.cache.provisional_ttl = 300

            from sovereign.cache import CacheReader, client_id
            from sovereign.cache.filesystem import FilesystemCache

            local = FilesystemCache(cache_path=temp_cache_dir)

            reader = CacheReader()
            reader.local = local
            reader.remote = None
            reader.register_over_http = MagicMock(return_value=True)

            cid = client_id(mock_cache_discovery_request)
            reader._register_and_upgrade_ttl(
                cid, mock_cache_discovery_request, mock_cache_entry
            )

            # Give the thread time to execute
            time.sleep(0.2)

            reader.register_over_http.assert_called_with(mock_cache_discovery_request)
            # Entry should be in local cache (upgraded to local_ttl on success)
            assert local.get(cid) is not None


class TestCacheWriter:
    """Tests for CacheWriter - dual-write logic."""

    def test_writes_to_both_caches(
        self, temp_cache_dir, mock_s3_bucket, mock_cache_entry
    ):
        """Set writes to both local and remote."""
        with patch("sovereign.cache.config") as cfg:
            cfg.cache.local_fs_path = temp_cache_dir
            cfg.cache.remote_backend = None
            cfg.cache.hash_rules = ["node.cluster"]

            from sovereign.cache import CacheWriter
            from sovereign.cache.backends.s3 import S3Backend
            from sovereign.cache.filesystem import FilesystemCache

            local = FilesystemCache(cache_path=temp_cache_dir)
            remote = S3Backend(
                {
                    "bucket_name": mock_s3_bucket["bucket_name"],
                    "prefix": mock_s3_bucket["prefix"],
                }
            )

            writer = CacheWriter()
            writer.local = local
            writer.remote = remote

            cached, _ = writer.set("key", mock_cache_entry)

            assert cached is True
            assert local.get("key") is not None
            assert remote.get("key") is not None

    def test_succeeds_if_one_cache_fails(
        self, temp_cache_dir, mock_s3_bucket, mock_cache_entry
    ):
        """Gracefully handles partial failure."""
        with patch("sovereign.cache.config") as cfg:
            cfg.cache.local_fs_path = temp_cache_dir
            cfg.cache.remote_backend = None
            cfg.cache.hash_rules = ["node.cluster"]

            from sovereign.cache import CacheWriter
            from sovereign.cache.backends.s3 import S3Backend
            from sovereign.cache.filesystem import FilesystemCache

            local = FilesystemCache(cache_path=temp_cache_dir)
            remote = S3Backend(
                {
                    "bucket_name": mock_s3_bucket["bucket_name"],
                    "prefix": mock_s3_bucket["prefix"],
                }
            )

            writer = CacheWriter()
            writer.local = local
            writer.remote = remote
            writer.remote.set = MagicMock(side_effect=Exception("S3 down"))

            cached, messages = writer.set("key", mock_cache_entry)

            assert cached is True  # Local succeeded
            assert any("remote" in m[1].lower() for m in messages)


class TestClientId:
    """Tests for client_id - deterministic cache key generation."""

    def test_same_request_produces_same_id(self, mock_cache_discovery_request):
        """Identical requests produce identical cache keys."""
        from sovereign.cache import client_id

        assert client_id(mock_cache_discovery_request) == client_id(
            mock_cache_discovery_request
        )

    def test_different_clusters_produce_different_ids(self):
        """Different node clusters produce different cache keys."""
        from sovereign.cache import client_id

        req1 = mock_discovery_request(
            resource_type="clusters", expressions=["cluster=A"]
        )
        req2 = mock_discovery_request(
            resource_type="clusters", expressions=["cluster=B"]
        )

        assert client_id(req1) != client_id(req2)


class TestCacheIntegration:
    """Integration tests for the full cache flow."""

    def test_stale_s3_entry_gets_refreshed(self, temp_cache_dir, mock_s3_bucket):
        """Fresh local write overwrites stale S3 entry."""
        from sovereign.cache.backends.s3 import S3Backend
        from sovereign.cache.filesystem import FilesystemCache

        local = FilesystemCache(cache_path=temp_cache_dir)
        remote = S3Backend(
            {
                "bucket_name": mock_s3_bucket["bucket_name"],
                "prefix": mock_s3_bucket["prefix"],
            }
        )

        stale = Entry(text="stale", len=0, version="v1", node=Node(cluster="c"))
        fresh = Entry(text="fresh", len=0, version="v2", node=Node(cluster="c"))

        remote.set("key", stale)
        local.set("key", fresh)
        remote.set("key", fresh)

        assert local.get("key").version == "v2"
        assert remote.get("key").version == "v2"


class TestCacheConfigValidation:
    """Tests for cache TTL configuration validation."""

    def test_provisional_ttl_greater_than_local_ttl_raises(self):
        """Should error if provisional_ttl > local_ttl."""

        from sovereign.configuration import CacheConfiguration

        with pytest.raises(ValueError, match="must not exceed"):
            CacheConfiguration(local_ttl=60, provisional_ttl=300)

    def test_negative_ttl_rejected(self):
        """Negative TTL values should be rejected."""
        from pydantic import ValidationError
        from sovereign.configuration import CacheConfiguration

        with pytest.raises(ValidationError):
            CacheConfiguration(local_ttl=-1)

    def test_infinite_local_ttl_allows_any_provisional(self):
        """When local_ttl is infinite (None or 0), any provisional_ttl is valid."""
        from sovereign.configuration import CacheConfiguration

        # Should not raise
        config1 = CacheConfiguration(local_ttl=None, provisional_ttl=9999)
        config2 = CacheConfiguration(local_ttl=0, provisional_ttl=9999)

        assert config1.provisional_ttl == 9999
        assert config2.provisional_ttl == 9999

    def test_provisional_ttl_zero_is_valid(self):
        """provisional_ttl=0 disables pessimistic caching."""
        from sovereign.configuration import CacheConfiguration

        config = CacheConfiguration(local_ttl=60, provisional_ttl=0)

        assert config.provisional_ttl == 0
        assert config.local_ttl == 60

    def test_default_ttl_values(self):
        """Default values should be 3600 for local_ttl and 300 for provisional_ttl."""
        from sovereign.configuration import CacheConfiguration

        config = CacheConfiguration()

        assert config.local_ttl == 3600
        assert config.provisional_ttl == 300
