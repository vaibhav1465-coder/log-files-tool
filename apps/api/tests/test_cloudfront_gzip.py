import gzip
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.intake import IntakeFailure, iter_analysis_lines, iter_preflight_lines
from app.parser import detect_profile, parse_cdn, preflight


CLOUDFRONT = (
    "2026-08-30\t05:00:01\tDEL54-P1\t1234\t203.0.113.5\tGET\t"
    "www.financialexpress.com\t/market/story\t200\t-\tGooglebot%2F2.1\tutm_source=test&page=2\n"
)


class CloudFrontAndGzipTests(unittest.TestCase):
    def test_cloudfront_standard_row_is_detected_and_parsed(self):
        self.assertEqual(detect_profile(CLOUDFRONT), "cdn_access")
        row = parse_cdn(CLOUDFRONT)
        self.assertEqual(row.path, "/market/story?utm_source=test&page=2")
        self.assertEqual(row.status, 200)
        self.assertEqual(row.response_bytes, 1234)
        self.assertEqual(row.user_agent, "Googlebot/2.1")
        self.assertEqual(row.timestamp.isoformat(), "2026-08-30T05:00:01+00:00")

    def test_cloudfront_headers_do_not_reduce_preflight_quality(self):
        result = preflight(iter(["#Version: 1.0\n", "#Fields: date time ...\n", CLOUDFRONT]))
        self.assertEqual(result.evidence_state, "passed")
        self.assertEqual(result.processed_lines, 1)
        self.assertEqual(result.accepted_lines, 1)

    def test_gzip_is_streamed_for_preflight_and_analysis(self):
        payload = gzip.compress(("#Version: 1.0\n" + CLOUDFRONT).encode())
        lines, entries = iter_preflight_lines(io.BytesIO(payload), "sample.gz")
        result = preflight(lines)
        self.assertEqual(entries, 1)
        self.assertEqual(result.evidence_state, "passed")

        lines, entries = iter_analysis_lines(io.BytesIO(payload), "sample.gz")
        self.assertEqual(entries, 1)
        self.assertEqual(list(lines), ["#Version: 1.0\n", CLOUDFRONT])

    def test_corrupt_gzip_is_rejected(self):
        lines, _ = iter_preflight_lines(io.BytesIO(b"not-gzip"), "sample.gz")
        with self.assertRaises(IntakeFailure):
            list(lines)


if __name__ == "__main__":
    unittest.main()
