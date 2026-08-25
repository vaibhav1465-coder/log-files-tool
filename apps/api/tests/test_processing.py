import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.processing import aggregate_lines, normalize_url


def cdn(path: str, status: int, timestamp: str = "18/Feb/2026:09:56:28 +0000") -> str:
    return f'42.118.137.185 - - [{timestamp}] "GET {path} HTTP/1.1" {status} 100 "-" "Googlebot/2.1"\n'


class ProcessingTests(unittest.TestCase):
    def test_normalization_removes_tracking_but_keeps_content_parameters(self):
        self.assertEqual(normalize_url("https://WWW.Example.com:443/story?utm_source=x&page=2#top"), "https://www.example.com/story?page=2")

    def test_aggregates_requests_urls_bytes_and_googlebot(self):
        summary = aggregate_lines([
            cdn("/story?utm_source=x", 200),
            cdn("/story", 200, "18/Feb/2026:10:56:28 +0000"),
            cdn("/missing", 404),
        ])
        self.assertEqual(summary.processed_lines, 3)
        self.assertEqual(summary.accepted_lines, 3)
        status_200 = next(row for row in summary.status_rows if row["status_code"] == 200)
        self.assertEqual(status_200["request_count"], 2)
        self.assertEqual(status_200["unique_url_count"], 1)
        story = next(row for row in summary.url_rows if row["normalized_url"] == "/story")
        self.assertEqual(story["googlebot_request_count"], 2)
        self.assertEqual(story["response_bytes"], 200)
        self.assertEqual(story["googlebot_first_seen"], "2026-02-18T09:56:28+00:00")
        self.assertEqual(story["googlebot_last_seen"], "2026-02-18T10:56:28+00:00")

    def test_resource_guard_and_progress_are_periodic_and_bounded(self):
        progress = []
        guards = []
        summary = aggregate_lines(
            [cdn(f"/story/{index}", 200) for index in range(5)],
            progress.append,
            resource_guard=lambda: guards.append(True),
            progress_interval=2,
            sink_batch_rows=1,
            sqlite_cache_mib=8,
        )
        self.assertEqual(summary.processed_lines, 5)
        self.assertEqual(progress, [2, 4])
        self.assertEqual(len(guards), 2)

if __name__ == "__main__":
    unittest.main()
