import unittest

from app.security import is_local_intake


class PrivateIntakeGuardTests(unittest.TestCase):
    def test_blocks_every_local_intake_route(self):
        self.assertTrue(is_local_intake("POST", "/api/v1/runs"))
        self.assertTrue(is_local_intake("POST", "/api/v1/preflight"))
        self.assertTrue(is_local_intake("POST", "/api/v1/uploads"))
        self.assertTrue(is_local_intake("PUT", "/api/v1/uploads/run-id/chunk"))

    def test_keeps_read_only_run_routes_available(self):
        self.assertFalse(is_local_intake("GET", "/api/v1/runs"))
        self.assertFalse(is_local_intake("GET", "/api/v1/runs/run-id"))
        self.assertFalse(is_local_intake("POST", "/api/v1/remote-runs"))


if __name__ == "__main__":
    unittest.main()
