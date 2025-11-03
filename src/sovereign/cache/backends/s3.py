import pickle
from typing import Any
from typing_extensions import override
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
