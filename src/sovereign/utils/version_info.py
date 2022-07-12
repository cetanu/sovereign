import zlib
from typing import Any


def compute_hash(*args: Any) -> str:
    """
    Creates a 'version hash' to be used in envoy Discovery Responses.
    """
    data: bytes = repr(args).encode()
    version_info = (
        zlib.crc32(data) & 0xFFFFFFFF
    )  # same numeric value across all py versions & platforms
    return str(version_info)
