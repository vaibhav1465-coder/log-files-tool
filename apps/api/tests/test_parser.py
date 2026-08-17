import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.parser import detect_profile, preflight


CDN = '42.118.137.185 - - [18/Feb/2026:09:56:28 +0000] "GET /news/story/ HTTP/1.1" 200 121849 "-" "Googlebot/2.1"\n'
ORIGIN = '{"body_bytes_sent":"25512","http_user_agent":"Googlebot","request_type":"GET","request_url":"/story","status":200,"timestamp_iso8601":"2026-02-18T10:55:07+00:00"}\n'


class ParserTests(unittest.TestCase):
    def test_detects_both_supplied_profiles(self):
        self.assertEqual(detect_profile(CDN), "cdn_access")
        self.assertEqual(detect_profile(ORIGIN), "origin_jsonl")

    def test_valid_cdn_passes(self):
        result = preflight([CDN])
        self.assertEqual(result.evidence_state, "passed")
        self.assertEqual(result.observed_statuses, {200: 1})

    def test_invalid_status_is_rejected_and_never_counted(self):
        result = preflight([CDN.replace(" 200 ", " 000 ")])
        self.assertEqual(result.evidence_state, "mapping_required")
        self.assertEqual(result.observed_statuses, {})
        self.assertEqual(result.rejection_reasons[0].reason, "STATUS_INVALID")

    def test_no_evidence_is_not_zero(self):
        result = preflight([])
        self.assertEqual(result.evidence_state, "no_data")
        self.assertIsNone(result.acceptance_rate)


if __name__ == "__main__":
    unittest.main()
