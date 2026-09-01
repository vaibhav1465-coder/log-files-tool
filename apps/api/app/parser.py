import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Literal
from urllib.parse import unquote

from .models import PreflightResult, RejectionSummary


Profile = Literal["cdn_access", "origin_jsonl", "unknown"]

CDN_PATTERN = re.compile(
    r'^(?P<ip>\S+) \S+ \S+ \[(?P<timestamp>[^\]]+)\] '
    r'"(?P<method>[A-Z]+) (?P<path>\S+) (?P<protocol>[^\"]+)" '
    r'(?P<status>\S+) (?P<bytes>\S+) "(?P<referrer>[^"]*)" "(?P<user_agent>[^"]*)"$'
)
TIMESTAMP_FORMAT = "%d/%b/%Y:%H:%M:%S %z"


@dataclass(frozen=True)
class ParsedRow:
    timestamp: datetime
    method: str
    path: str
    status: int
    response_bytes: int | None
    user_agent: str


class ParseFailure(ValueError):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _cloudfront_fields(line: str) -> list[str] | None:
    fields = line.rstrip("\r\n").split("\t")
    if len(fields) < 12 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fields[0]):
        return None
    if not re.fullmatch(r"\d{2}:\d{2}:\d{2}(?:\.\d+)?", fields[1]):
        return None
    return fields


def detect_profile(line: str) -> Profile:
    stripped = line.lstrip()
    if stripped.startswith("{"):
        return "origin_jsonl"
    if CDN_PATTERN.match(line.rstrip("\r\n")) or _cloudfront_fields(line):
        return "cdn_access"
    return "unknown"


def _status(value: object) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ParseFailure("STATUS_INVALID") from exc
    if result < 100 or result > 599:
        raise ParseFailure("STATUS_INVALID")
    return result


def _bytes(value: object) -> int | None:
    if value in (None, "", "-"):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ParseFailure("BYTES_INVALID") from exc
    if result < 0:
        raise ParseFailure("BYTES_INVALID")
    return result


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value:
        raise ParseFailure("TIMESTAMP_INVALID")
    try:
        return datetime.strptime(value, TIMESTAMP_FORMAT)
    except ValueError:
        try:
            result = datetime.fromisoformat(value)
            return result if result.tzinfo else result.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ParseFailure("TIMESTAMP_INVALID") from exc


def _parse_cloudfront(fields: list[str]) -> ParsedRow:
    path = unquote(fields[7])
    query = fields[11]
    if query not in {"", "-"}:
        path = f"{path}?{query}"
    if not path:
        raise ParseFailure("PATH_MISSING")
    return ParsedRow(
        timestamp=_timestamp(f"{fields[0]}T{fields[1]}+00:00"),
        method=fields[5],
        path=path,
        status=_status(fields[8]),
        response_bytes=_bytes(fields[3]),
        user_agent=unquote(fields[10]),
    )


def parse_cdn(line: str) -> ParsedRow:
    cloudfront = _cloudfront_fields(line)
    if cloudfront:
        return _parse_cloudfront(cloudfront)
    match = CDN_PATTERN.match(line.rstrip("\r\n"))
    if not match:
        raise ParseFailure("FIELD_COUNT_MISMATCH")
    values = match.groupdict()
    path = unquote(values["path"])
    if not path:
        raise ParseFailure("PATH_MISSING")
    return ParsedRow(
        timestamp=_timestamp(values["timestamp"]),
        method=values["method"],
        path=path,
        status=_status(values["status"]),
        response_bytes=_bytes(values["bytes"]),
        user_agent=unquote(values["user_agent"]),
    )


def parse_origin(line: str) -> ParsedRow:
    try:
        values = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ParseFailure("FIELD_COUNT_MISMATCH") from exc
    path = values.get("request_url")
    if not path:
        raise ParseFailure("PATH_MISSING")
    method = values.get("request_type")
    if not isinstance(method, str) or not method:
        raise ParseFailure("METHOD_INVALID")
    return ParsedRow(
        timestamp=_timestamp(values.get("timestamp_iso8601") or values.get("timestamp")),
        method=method,
        path=path,
        status=_status(values.get("status")),
        response_bytes=_bytes(values.get("body_bytes_sent")),
        user_agent=str(values.get("http_user_agent") or ""),
    )


def preflight(lines: Iterable[str], limit: int = 10_000, minimum_acceptance_rate: float = 0.95) -> PreflightResult:
    processed = accepted = 0
    statuses: Counter[int] = Counter()
    rejections: Counter[str] = Counter()
    timestamps: list[datetime] = []
    profile: Profile = "unknown"

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if processed >= limit:
            break
        processed += 1
        if profile == "unknown":
            profile = detect_profile(line)
        try:
            if profile == "cdn_access":
                row = parse_cdn(line)
            elif profile == "origin_jsonl":
                row = parse_origin(line)
            else:
                raise ParseFailure("UNKNOWN_FORMAT")
        except ParseFailure as exc:
            rejections[exc.reason] += 1
            continue
        accepted += 1
        statuses[row.status] += 1
        timestamps.append(row.timestamp)

    rejected = processed - accepted
    acceptance_rate = accepted / processed if processed else None
    evidence_state = "no_data" if not processed else (
        "passed" if acceptance_rate is not None and acceptance_rate >= minimum_acceptance_rate else "mapping_required"
    )
    return PreflightResult(
        profile=profile,
        processed_lines=processed,
        accepted_lines=accepted,
        rejected_lines=rejected,
        acceptance_rate=acceptance_rate,
        timestamp_parse_rate=acceptance_rate,
        valid_status_rate=acceptance_rate,
        evidence_state=evidence_state,
        rejection_reasons=[RejectionSummary(reason=k, count=v) for k, v in rejections.most_common()],
        observed_statuses=dict(sorted(statuses.items())),
        observed_time_start=min(timestamps) if timestamps else None,
        observed_time_end=max(timestamps) if timestamps else None,
    )
