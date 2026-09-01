from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import boto3

from .remote_sources import configured_sources


def _approved_s3_path(settings: Any, bucket: str, key: str) -> bool:
    return any(
        source.bucket == bucket
        and (key == source.prefix.rstrip("/") or key.startswith(source.prefix.rstrip("/") + "/"))
        for source in configured_sources(settings).values()
    )


@contextmanager
def open_source_stream(settings: Any, stored_path: str, s3_client: Any | None = None) -> Iterator[Any]:
    if not stored_path.startswith("s3://"):
        with Path(stored_path).open("rb") as local:
            yield local
        return

    parsed = urlparse(stored_path)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key or not _approved_s3_path(settings, bucket, key):
        raise PermissionError("Remote source path is outside the configured read-only allowlist.")

    client = s3_client or boto3.client("s3")
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    try:
        yield body
    finally:
        body.close()
