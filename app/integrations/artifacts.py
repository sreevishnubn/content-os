"""Resolve production artifacts from worker-accessible storage.

Workers may register a local path during local development or a remote
HTTP(S)/S3 URI in hosted production. Remote artifacts are downloaded to
temporary storage before integrations such as YouTube consume them.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def materialize_artifact(uri: str) -> tuple[str, bool]:
    """Return a local path and whether the caller owns the temporary file."""
    value = str(uri).strip()
    parsed = urlparse(value)

    if parsed.scheme in ("", "file"):
        path = parsed.path if parsed.scheme == "file" else value
        if not Path(path).exists():
            raise FileNotFoundError(f"Production artifact does not exist: {value}")
        return path, False

    if parsed.scheme in ("http", "https"):
        suffix = Path(parsed.path).suffix or ".mp4"
        fd, destination = tempfile.mkstemp(prefix="contentos-artifact-", suffix=suffix)
        os.close(fd)
        request = Request(value, headers={"User-Agent": "ContentOS/1.0"})
        try:
            with urlopen(request, timeout=120) as response, open(destination, "wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
        except Exception:
            Path(destination).unlink(missing_ok=True)
            raise
        return destination, True

    if parsed.scheme == "s3":
        import boto3

        if not parsed.netloc or not parsed.path.strip("/"):
            raise ValueError(f"Invalid S3 artifact URI: {value}")
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        suffix = Path(key).suffix or ".mp4"
        fd, destination = tempfile.mkstemp(prefix="contentos-artifact-", suffix=suffix)
        os.close(fd)
        try:
            boto3.client("s3").download_file(bucket, key, destination)
        except Exception:
            Path(destination).unlink(missing_ok=True)
            raise
        return destination, True

    raise ValueError(
        "Unsupported production artifact URI. Use a local path, HTTPS URL, "
        "or s3://bucket/key URI."
    )
