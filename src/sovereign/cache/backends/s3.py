import pickle
from datetime import datetime, timedelta, timezone
from importlib.util import find_spec
from typing import Any
from urllib.parse import quote

from typing_extensions import override

from sovereign import application_logger as log
from sovereign.cache.backends import CacheBackend

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    pass

BOTO_AVAILABLE = find_spec("boto3") is not None


class S3Client:
    def __init__(self, role_arn: str | None, client_args: dict[str, Any]):
        self.role_arn = role_arn
        self.client_args = client_args
        self._client = None
        self._credentials_expiry = None
        self._base_session = boto3.Session()
        self._make_client()

    def _make_client(self) -> None:
        if self.role_arn:
            log.debug(f"Refreshing credentials for role: {self.role_arn}")
            sts = self._base_session.client("sts")
            duration_seconds = 3600  # 4 hours
            response = sts.assume_role(
                RoleArn=self.role_arn,
                RoleSessionName="sovereign-s3-cache",
                DurationSeconds=duration_seconds,
            )
            credentials = response["Credentials"]
            session = boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
            )
            self._credentials_expiry = credentials["Expiration"]
        else:
            session = self._base_session
            self._credentials_expiry = None
        self._client = session.client("s3", **self.client_args)

    def _session_expiring_soon(self) -> bool:
        if not self.role_arn or self._credentials_expiry is None:
            return False
        refresh_threshold = timedelta(minutes=30).seconds
        time_until_expiry = (
            self._credentials_expiry - datetime.now(timezone.utc)
        ).total_seconds()
        return time_until_expiry <= refresh_threshold

    def __getattr__(self, name):
        if self._session_expiring_soon():
            self._make_client()
        return getattr(self._client, name)


class S3Backend(CacheBackend):
    """S3 cache backend implementation"""

    @override
    def __init__(self, config: dict[str, Any]) -> None:  # pyright: ignore[reportMissingSuperCall]
        """Initialize S3 backend

        Args:
            config: Configuration dictionary containing S3 connection parameters
                   Expected keys: bucket_name, prefix
                   Optional keys: assume_role, endpoint_url
        """
        if not BOTO_AVAILABLE:
            raise ImportError("boto3 not installed")

        self.bucket_name = config.get("bucket_name")
        if not self.bucket_name:
            raise ValueError("bucket_name is required for S3 cache backend")

        self.prefix = config.get("prefix", "sovereign-cache")
        self.registration_prefix = config.get("registration_prefix", "registrations-")
        self.role = config.get("assume_role")

        client_args: dict[str, Any] = {}
        if endpoint_url := config.get("endpoint_url"):
            client_args["endpoint_url"] = endpoint_url

        self.client_args = client_args
        self.s3 = S3Client(self.role, self.client_args)

        try:
            self.s3.head_bucket(Bucket=self.bucket_name)
            log.info(f"S3 cache backend connected to bucket '{self.bucket_name}'")
        except Exception as e:
            log.error(
                f"Failed to access S3 bucket '{self.bucket_name}' with current credentials: {e}"
            )
            raise

    def _make_key(self, key: str) -> str:
        encoded_key = quote(key, safe="")
        return f"{self.prefix}/{encoded_key}"

    def get(self, key: str) -> Any | None:
        try:
            log.debug(f"Retrieving object {key} from bucket")
            response = self.s3.get_object(
                Bucket=self.bucket_name, Key=self._make_key(key)
            )
            data = response["Body"].read()
            unpickled = pickle.loads(data)
            log.debug(f"Successfully obtained object {key} from bucket")
            return unpickled
        except self.s3.exceptions.NoSuchKey:
            log.debug(f"{key} not in bucket")
            return None
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                log.debug(f"{key} not in bucket")
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
