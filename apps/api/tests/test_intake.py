import io
import sys
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.intake import IntakeFailure, iter_analysis_lines, iter_preflight_lines


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

    def test_analysis_limit_stops_plain_file_on_line_boundary(self):
        lines, _ = iter_analysis_lines(io.BytesIO(b"one\ntwo\nthree\n"), "sample.log", max_bytes=8)
        self.assertEqual(list(lines), ["one\n", "two\n"])

    def test_analysis_limit_scales_safely_for_zip(self):
        source = self.make_zip("logs/sample.log", "one\ntwo\nthree\nfour\n")
        compressed_size = len(source.getvalue())
        lines, _ = iter_analysis_lines(source, "sample.zip", max_bytes=max(1, compressed_size // 2), source_size_bytes=compressed_size)
        selected = list(lines)
        self.assertGreater(len(selected), 0)
        self.assertLess(len(selected), 4)

if __name__ == "__main__":
    unittest.main()
