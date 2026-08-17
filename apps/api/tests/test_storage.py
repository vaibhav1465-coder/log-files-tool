import tempfile
import unittest
from pathlib import Path

from app.storage import append_chunk, finalize_upload


class StorageTests(unittest.TestCase):
    def test_chunks_require_exact_offset_and_finalize_without_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "source.log.uploading"
            self.assertEqual(append_chunk(target, 0, b"first"), 5)
            with self.assertRaises(ValueError):
                append_chunk(target, 0, b"duplicate")
            self.assertEqual(append_chunk(target, 5, b"second"), 11)
            stored = finalize_upload(target, 11)
            self.assertEqual(stored.path.read_bytes(), b"firstsecond")
            self.assertFalse(target.exists())
            self.assertEqual(stored.size_bytes, 11)

    def test_incomplete_upload_cannot_finalize(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "source.log.uploading"
            target.write_bytes(b"short")
            with self.assertRaises(ValueError):
                finalize_upload(target, 10)


if __name__ == "__main__":
    unittest.main()
