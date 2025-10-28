import pickle
from typing import Any, override
from urllib.parse import quote

from sovereign import application_logger as log
from sovereign.cache.backends import CacheBackend


from importlib.util import find_spec

if find_spec("boto3"):
    import boto3
    from botocore.exceptions import ClientError

    class S3Backend(CacheBackend):
        """S3 cache backend implementation"""

        @override
        def __init__(self, config: dict[str, Any]) -> None:  # pyright: ignore[reportMissingSuperCall]
            """Initialize S3 backend

            Args:
                config: Configuration dictionary containing S3 connection parameters
                       Expected keys: bucket_name, key
            """
            self.bucket_name = config.get("bucket_name")
            if not self.bucket_name:
                raise ValueError("bucket_name is required for S3 cache backend")

            self.key = config.get("key", "sovereign-cache/")
            self.s3_client = boto3.client("s3")

            # Test connection by checking if bucket exists
            try:
                self.s3_client.head_bucket(Bucket=self.bucket_name)
                log.info(f"S3 cache backend connected to bucket '{self.bucket_name}'")
            except Exception as e:
                log.error(f"Failed to access S3 bucket '{self.bucket_name}': {e}")
                raise

        def _make_key(self, key: str) -> str:
            encoded_key = quote(key, safe="")
            return f"{self.key}{encoded_key}"

        def get(self, key: str) -> Any | None:
            try:
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name, Key=self._make_key(key)
                )
                data = response["Body"].read()
                return pickle.loads(data)
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
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=self._make_key(key),
                    Body=pickle.dumps(value),
                )
            except Exception as e:
                log.warning(f"Failed to set key '{key}' in S3: {e}")
                raise
