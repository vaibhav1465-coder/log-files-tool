import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import hash_password, verify_password


class PasswordHashTests(unittest.TestCase):
    def test_scrypt_round_trip(self):
        encoded = hash_password("a-strong-temporary-password")
        self.assertTrue(encoded.startswith("scrypt$"))
        self.assertTrue(verify_password("a-strong-temporary-password", encoded))
        self.assertFalse(verify_password("wrong-password-value", encoded))
        self.assertNotIn("a-strong-temporary-password", encoded)

    def test_malformed_hash_fails_closed(self):
        self.assertFalse(verify_password("anything-long-enough", "not-a-valid-hash"))


if __name__ == "__main__":
    unittest.main()
