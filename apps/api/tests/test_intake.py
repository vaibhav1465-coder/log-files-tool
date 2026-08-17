import io
import sys
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.intake import IntakeFailure, iter_preflight_lines


class IntakeTests(unittest.TestCase):
    def make_zip(self, name: str, content: str) -> io.BytesIO:
        output = io.BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            archive.writestr(name, content)
        output.seek(0)
        return output

    def test_streams_safe_zip_entry(self):
        lines, entries = iter_preflight_lines(self.make_zip("logs/sample.log", "one\ntwo\n"), "sample.zip")
        self.assertEqual(entries, 1)
        self.assertEqual(list(lines), ["one\n", "two\n"])

    def test_rejects_path_traversal(self):
        with self.assertRaises(IntakeFailure) as raised:
            iter_preflight_lines(self.make_zip("../escape.log", "bad"), "sample.zip")
        self.assertEqual(raised.exception.code, "ARCHIVE_PATH_REJECTED")


if __name__ == "__main__":
    unittest.main()
