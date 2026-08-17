import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.gsc import GscClient


class GscClientTests(unittest.TestCase):
    def test_search_analytics_paginates_and_preserves_property_encoding(self):
        client = object.__new__(GscClient)
        calls = []

        def request(method, url, **kwargs):
            calls.append((method, url, kwargs["json"]))
            return {"rows": []}

        client.request = request
        result = client.search_performance("sc-domain:example.com", date(2026, 1, 1), date(2026, 1, 28))
        self.assertEqual(result, [])
        self.assertIn("sc-domain%3Aexample.com", calls[0][1])
        self.assertEqual(calls[0][2]["dimensions"], ["date", "page"])
        self.assertEqual(calls[0][2]["rowLimit"], 25000)

    def test_inspection_uses_official_endpoint_and_scope_fields(self):
        client = object.__new__(GscClient)
        captured = {}

        def request(method, url, **kwargs):
            captured.update(method=method, url=url, payload=kwargs["json"])
            return {"inspectionResult": {"indexStatusResult": {"verdict": "PASS"}}}

        client.request = request
        result = client.inspect_url("sc-domain:example.com", "https://example.com/story")
        self.assertEqual(result["indexStatusResult"]["verdict"], "PASS")
        self.assertEqual(captured["url"], "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect")
        self.assertEqual(captured["payload"]["siteUrl"], "sc-domain:example.com")


if __name__ == "__main__":
    unittest.main()
