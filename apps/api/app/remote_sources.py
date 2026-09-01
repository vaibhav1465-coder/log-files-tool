from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable


class RemoteSourceError(ValueError):
    pass


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    label: str
    provider: str
    bucket: str
    prefix: str


@dataclass(frozen=True)
class RemoteObject:
    bucket: str
    key: str
    size_bytes: int
    etag: str
    last_modified: str | None

    @property
    def uri(self) -> str:
        return f"s3://{self.bucket}/{self.key}"

    def public_metadata(self) -> dict[str, Any]:
        return {
            "filename": self.key.rsplit("/", 1)[-1],
            "size_bytes": self.size_bytes,
            "last_modified": self.last_modified,
        }


def configured_sources(settings: Any) -> dict[str, SourceDefinition]:
    candidates = [
        SourceDefinition(
            id="financial-express-cloudfront",
            label="Financial Express — CloudFront",
            provider="CloudFront",
            bucket=settings.fe_cloudfront_bucket,
            prefix=settings.fe_cloudfront_prefix,
        ),
        SourceDefinition(
            id="financial-express-akamai",
            label="Financial Express — Akamai",
            provider="Akamai",
            bucket=settings.fe_akamai_bucket,
            prefix=settings.fe_akamai_prefix,
        ),
    ]
    return {item.id: item for item in candidates if item.bucket and item.prefix}


def source_catalog(settings: Any) -> list[dict[str, str]]:
    return [
        {"id": item.id, "label": item.label, "provider": item.provider, "timezone": "UTC"}
        for item in configured_sources(settings).values()
    ]


def get_source(settings: Any, source_id: str) -> SourceDefinition:
    try:
        return configured_sources(settings)[source_id]
    except KeyError as exc:
        raise RemoteSourceError("Source is not configured or approved for this pilot.") from exc


def validate_hours(start_hour: int, end_hour: int) -> range:
    if not 0 <= start_hour < end_hour <= 24:
        raise RemoteSourceError("Choose a UTC hour range between 00:00 and 24:00.")
    return range(start_hour, end_hour)


def _cloudfront_prefixes(source: SourceDefinition, day: date, hours: Iterable[int]) -> list[str]:
    return [f"{source.prefix.rstrip('/')}/{day:%Y/%m/%d}/{hour:02d}/" for hour in hours]


def _akamai_markers(day: date, hours: Iterable[int]) -> set[str]:
    return {f".{day:%Y%m%d}{hour:02d}00-{(hour + 1) % 24:02d}00-" for hour in hours}


def _page_objects(page: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for item in page.get("Contents", []):
        key = str(item.get("Key", ""))
        if key and not key.endswith("/"):
            yield item


def _mapped(source: SourceDefinition, item: dict[str, Any]) -> RemoteObject:
    modified = item.get("LastModified")
    return RemoteObject(
        bucket=source.bucket,
        key=str(item["Key"]),
        size_bytes=int(item.get("Size", 0)),
        etag=str(item.get("ETag", "")).strip('"'),
        last_modified=modified.isoformat() if hasattr(modified, "isoformat") else (str(modified) if modified else None),
    )


def discover_objects(
    s3_client: Any,
    source: SourceDefinition,
    day: date,
    start_hour: int,
    end_hour: int,
    *,
    max_objects: int,
    max_total_bytes: int,
    max_scanned_keys: int = 1_000_000,
) -> list[RemoteObject]:
    hours = validate_hours(start_hour, end_hour)
    paginator = s3_client.get_paginator("list_objects_v2")
    found: list[RemoteObject] = []
    scanned = 0

    if source.provider == "CloudFront":
        for prefix in _cloudfront_prefixes(source, day, hours):
            for page in paginator.paginate(Bucket=source.bucket, Prefix=prefix):
                for item in _page_objects(page):
                    scanned += 1
                    found.append(_mapped(source, item))
    elif source.provider == "Akamai":
        markers = _akamai_markers(day, hours)
        for page in paginator.paginate(Bucket=source.bucket, Prefix=source.prefix):
            for item in _page_objects(page):
                scanned += 1
                if scanned > max_scanned_keys:
                    raise RemoteSourceError("The source index is too large for a safe interactive scan.")
                key = str(item["Key"])
                if any(marker in key for marker in markers):
                    found.append(_mapped(source, item))
    else:
        raise RemoteSourceError("Source provider is not supported.")

    objects = sorted({item.key: item for item in found}.values(), key=lambda item: item.key)
    if not objects:
        raise RemoteSourceError("No log files were found for the selected UTC period.")
    if len(objects) > max_objects:
        raise RemoteSourceError(f"Selection contains {len(objects)} files; the pilot limit is {max_objects}.")
    total = sum(item.size_bytes for item in objects)
    if total > max_total_bytes:
        raise RemoteSourceError(f"Selection exceeds the pilot byte limit for one run.")
    return objects
