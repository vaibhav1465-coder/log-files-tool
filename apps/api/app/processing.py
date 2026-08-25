import re
import sqlite3
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlsplit, urlunsplit

from .parser import ParseFailure, ParsedRow, detect_profile, parse_cdn, parse_origin


TRACKING_PARAMETERS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}


def normalize_url(value: str) -> str:
    if value.startswith("/"):
        path, _, query = value.partition("?")
        kept = [part for part in query.split("&") if part and part.split("=", 1)[0].lower() not in TRACKING_PARAMETERS]
        return path + (f"?{'&'.join(kept)}" if kept else "")
    parts = urlsplit(value)
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host if not port or (parts.scheme.lower() == "https" and port == 443) or (parts.scheme.lower() == "http" and port == 80) else f"{host}:{port}"
    kept = [part for part in parts.query.split("&") if part and part.split("=", 1)[0].lower() not in TRACKING_PARAMETERS]
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "/", "&".join(kept), ""))


@dataclass(frozen=True)
class ProcessingSummary:
    profile: str
    processed_lines: int
    accepted_lines: int
    rejected_lines: int
    rejection_reasons: dict[str, int]
    status_rows: list[dict]
    url_rows: list[dict]


def aggregate_lines(
    lines: Iterable[str],
    progress: Callable[[int], None] | None = None,
    url_sink: Callable[[list[dict]], None] | None = None,
    scratch_directory: Path | None = None,
    resource_guard: Callable[[], None] | None = None,
    progress_interval: int = 10_000,
    sink_batch_rows: int = 2_000,
    sqlite_cache_mib: int = 64,
) -> ProcessingSummary:
    processed = accepted = 0
    profile = "unknown"
    rejections: Counter[str] = Counter()
    temp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False, dir=scratch_directory)
    temp.close()
    db_path = Path(temp.name)
    conn = sqlite3.connect(db_path)
    # Bound memory and keep scratch state to one primary file for huge runs.
    conn.execute("PRAGMA journal_mode=DELETE")
    conn.execute("PRAGMA temp_store=FILE")
    conn.execute(f"PRAGMA cache_size=-{max(8, sqlite_cache_mib) * 1024}")
    conn.execute("CREATE TABLE urls (url TEXT, status INTEGER, requests INTEGER, first_seen TEXT, last_seen TEXT, bytes INTEGER, googlebot INTEGER, googlebot_first TEXT, googlebot_last TEXT, PRIMARY KEY(url,status))")
    try:
        for line in lines:
            if not line.strip():
                continue
            processed += 1
            if profile == "unknown":
                profile = detect_profile(line)
            try:
                row: ParsedRow = parse_cdn(line) if profile == "cdn_access" else parse_origin(line) if profile == "origin_jsonl" else (_ for _ in ()).throw(ParseFailure("UNKNOWN_FORMAT"))
            except ParseFailure as exc:
                rejections[exc.reason] += 1
                continue
            accepted += 1
            normalized = normalize_url(row.path)
            is_googlebot = 1 if re.search(r"googlebot", row.user_agent, re.IGNORECASE) else 0
            bot_time = row.timestamp.isoformat() if is_googlebot else None
            conn.execute(
                "INSERT INTO urls VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(url,status) DO UPDATE SET requests=requests+1, first_seen=MIN(first_seen,excluded.first_seen), last_seen=MAX(last_seen,excluded.last_seen), bytes=COALESCE(bytes,0)+COALESCE(excluded.bytes,0), googlebot=googlebot+excluded.googlebot, googlebot_first=CASE WHEN excluded.googlebot_first IS NULL THEN googlebot_first WHEN googlebot_first IS NULL THEN excluded.googlebot_first ELSE MIN(googlebot_first,excluded.googlebot_first) END, googlebot_last=CASE WHEN excluded.googlebot_last IS NULL THEN googlebot_last WHEN googlebot_last IS NULL THEN excluded.googlebot_last ELSE MAX(googlebot_last,excluded.googlebot_last) END",
                (normalized, row.status, 1, row.timestamp.isoformat(), row.timestamp.isoformat(), row.response_bytes, is_googlebot, bot_time, bot_time),
            )
            if processed % max(1, progress_interval) == 0:
                conn.commit()
                if progress:
                    progress(processed)
                if resource_guard:
                    resource_guard()
        conn.commit()
        columns = ("normalized_url", "status_code", "request_count", "first_seen", "last_seen", "response_bytes", "googlebot_request_count", "googlebot_first_seen", "googlebot_last_seen")
        cursor = conn.execute("SELECT url,status,requests,first_seen,last_seen,bytes,googlebot,googlebot_first,googlebot_last FROM urls")
        url_rows: list[dict] = []
        while batch := cursor.fetchmany(max(1, sink_batch_rows)):
            mapped = [dict(zip(columns, row)) for row in batch]
            if url_sink:
                url_sink(mapped)
            else:
                url_rows.extend(mapped)
        status_rows = [dict(zip(("status_code", "request_count", "unique_url_count", "response_bytes"), row)) for row in conn.execute("SELECT status,SUM(requests),COUNT(*),SUM(bytes) FROM urls GROUP BY status ORDER BY status")]
        return ProcessingSummary(profile, processed, accepted, processed - accepted, dict(rejections), status_rows, url_rows)
    finally:
        conn.close()
        db_path.unlink(missing_ok=True)
        db_path.with_name(db_path.name + "-journal").unlink(missing_ok=True)
