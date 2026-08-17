import csv
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.exports import csv_lines, safe_csv_value


class ExportTests(unittest.TestCase):
    def test_formula_injection_is_neutralized(self):
        for prefix in "=+-@":
            self.assertEqual(safe_csv_value(prefix + "danger"), "'" + prefix + "danger")

    def test_csv_has_stable_headers_and_escaped_values(self):
        output = "".join(csv_lines([{"run_id": "one", "url": '=cmd("x")', "status": 200}]))
        rows = list(csv.DictReader(io.StringIO(output)))
        self.assertEqual(rows[0]["url"], "'=cmd(\"x\")")
        self.assertEqual(rows[0]["status"], "200")


if __name__ == "__main__":
    unittest.main()
