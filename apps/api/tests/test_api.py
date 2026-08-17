import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_cdn_preflight(self):
        sample = b'42.118.137.185 - - [18/Feb/2026:09:56:28 +0000] "GET /news/story/ HTTP/1.1" 200 121849 "-" "Googlebot/2.1"\n'
        response = self.client.post(
            "/api/v1/preflight",
            data={"source_type": "cdn"},
            files=[("files", ("sample.log", sample, "text/plain"))],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["quality_gate"], "passed")

    def test_source_mismatch_requires_mapping(self):
        sample = b'{"body_bytes_sent":"1","request_type":"GET","request_url":"/","status":200,"timestamp_iso8601":"2026-02-18T10:55:07+00:00"}\n'
        response = self.client.post(
            "/api/v1/preflight",
            data={"source_type": "cdn"},
            files=[("files", ("sample.jsonl", sample, "application/json"))],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["quality_gate"], "mapping_required")


if __name__ == "__main__":
    unittest.main()
