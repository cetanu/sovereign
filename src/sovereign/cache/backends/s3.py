import time
import pickle
from typing import Any
from typing_extensions import cast, override
from urllib.parse import quote
from importlib.util import find_spec

import pydantic

from sovereign import application_logger as log
from sovereign.cache.backends import CacheBackend
from sovereign.schemas import DiscoveryRequest

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    pass

BOTO_AVAILABLE = find_spec("boto3") is not None


class CompactedClients(pydantic.BaseModel):
    clients: list[tuple[str, DiscoveryRequest]]


class S3Backend(CacheBackend):
    """S3 cache backend implementation"""

    @override
    def __init__(self, config: dict[str, Any]) -> None:  # pyright: ignore[reportMissingSuperCall]
        """Initialize S3 backend

        Args:
            config: Configuration dictionary containing S3 connection parameters
                   Expected keys: bucket_name, key
                   Optional keys: endpoint_url
        """
        if not BOTO_AVAILABLE:
            raise ImportError("boto3 not installed")
        self.bucket_name = config.get("bucket_name")
        if not self.bucket_name:
            raise ValueError("bucket_name is required for S3 cache backend")

        self.key = config.get("key", "sovereign-cache/")
        self.registration_prefix = config.get("registration_prefix", "registrations-")
        self.compaction_threshold = config.get("compaction_threshold", 100)

        client_args = {}
        if endpoint_url := config.get("endpoint_url"):
            client_args["endpoint_url"] = endpoint_url

        self.s3 = boto3.client("s3", **client_args)

        # Test connection by checking if bucket exists
        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
            log.info(f"S3 cache backend connected to bucket '{self.bucket_name}'")
        except Exception as e:
            log.error(f"Failed to access S3 bucket '{self.bucket_name}': {e}")
            raise

    def _make_key(self, key: str) -> str:
        encoded_key = quote(key, safe="")
        return f"{self.key}{encoded_key}"

    def get(self, key: str) -> Any | None:
        try:
            log.debug(f"Retrieving object {key} from bucket")
            response = self.s3.get_object(
                Bucket=self.bucket_name, Key=self._make_key(key)
            )
            data = response["Body"].read()
            return pickle.loads(data)
        except self.s3.exceptions.NoSuchKey:
            return None
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None
            log.warning(f"Failed to get key '{key}' from S3: {e}")
            return None
        except Exception as e:
            log.warning(f"Failed to get key '{key}' from S3: {e}")
            return None

    @override
    def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        try:
            log.debug(f"Putting new object {key} into bucket")
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=self._make_key(key),
                Body=pickle.dumps(value),
            )
        except Exception as e:
            log.warning(f"Failed to set key '{key}' in S3: {e}")
            raise

    def _make_registration_key(self, id: str, timestamp: float) -> str:
        """Create a timestamped key for registration entries"""
        return f"{self.registration_prefix}{timestamp:.6f}-{id}.json"

    def _get_registration_entries(self) -> list[tuple[str, DiscoveryRequest]]:
        """Get all registration entries from S3, ordered by timestamp"""
        try:
            log.debug("Retrieving client list")
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name, Prefix=self.registration_prefix
            )

            if "Contents" not in response:
                log.debug("No contents found")
                return []

            compacted = CompactedClients(clients=[])
            for obj in sorted(response["Contents"], key=lambda x: x["Key"]):
                try:
                    obj_response = self.s3.get_object(
                        Bucket=self.bucket_name, Key=obj["Key"]
                    )
                    req = DiscoveryRequest.model_validate_json(
                        obj_response["Body"].read().decode("utf-8")
                    )
                    _prefix, _timestamp, filename = obj["Key"].split("-")
                    id = cast(str, filename).removesuffix(".json")
                    compacted.clients.append((id, req))
                except Exception as e:
                    log.warning(f"Failed to read registration entry {obj['Key']}: {e}")
                    continue

            log.debug("Found client entries")
            return compacted.clients
        except Exception as e:
            log.warning(f"Failed to list registration entries: {e}")
            return []

    def _compact_registrations(
        self, entries: list[tuple[str, DiscoveryRequest]]
    ) -> None:
        try:
            compacted_key = (
                f"{self.registration_prefix}-compacted-{time.time():.6f}.json"
            )
            self.s3.put_object(
                Bucket=self.bucket_name,
                Key=compacted_key,
                Body=CompactedClients(clients=entries).model_dump_json(),
            )

            # Delete old individual entries
            response = self.s3.list_objects_v2(
                Bucket=self.bucket_name, Prefix=self.registration_prefix
            )
            if "Contents" in response:
                objects_to_delete = [
                    {"Key": obj["Key"]}
                    for obj in response["Contents"]
                    if obj["Key"] != compacted_key
                ]
                if objects_to_delete:
                    self.s3.delete_objects(
                        Bucket=self.bucket_name, Delete={"Objects": objects_to_delete}
                    )

            log.debug(
                f"Compacted {len(entries)} registration entries into {compacted_key}"
            )

        except Exception as e:
            log.warning(f"Failed to compact registration entries: {e}")

    @override
    def register(self, id: str, req: DiscoveryRequest) -> None:
        try:
            timestamp = time.time()

            key = self._make_registration_key(id, timestamp)
            self.s3.put_object(
                Bucket=self.bucket_name, Key=key, Body=req.model_dump_json()
            )

            log.debug(f"Registered client {id} with timestamp {timestamp}")

            # Check if compaction is needed
            entries = self._get_registration_entries()
            if len(entries) > self.compaction_threshold:
                self._compact_registrations(entries)

        except Exception as e:
            log.warning(f"Failed to register client '{id}': {e}")
            raise

    @override
    def registered(self, id: str) -> bool:
        try:
            for entry in self._get_registration_entries():
                cid, _ = entry
                if cid == id:
                    return True
            return False

        except Exception as e:
            log.warning(f"Failed to check if client '{id}' is registered: {e}")
            return False

    @override
    def get_registered_clients(self) -> list[tuple[str, DiscoveryRequest]]:
        try:
            return self._get_registration_entries()
        except Exception as e:
            log.warning(f"Failed to get registered clients: {e}")
            return []
