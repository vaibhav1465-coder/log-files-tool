import csv
import io
from collections.abc import Iterable, Iterator


CSV_HEADERS = [
    "run_id", "publication", "source_type", "url", "status", "request_count",
    "googlebot_request_count", "first_seen", "last_seen", "response_bytes", "evidence_quality",
]


def safe_csv_value(value: object) -> object:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def csv_lines(rows: Iterable[dict]) -> Iterator[str]:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_HEADERS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    for row in rows:
        writer.writerow({key: safe_csv_value(row.get(key, "")) for key in CSV_HEADERS})
        yield buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
