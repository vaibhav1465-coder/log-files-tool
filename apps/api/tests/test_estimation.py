import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.estimation import estimate_seconds


class EstimationTests(unittest.TestCase):
    def test_estimate_is_ordered_and_scales(self):
        small = estimate_seconds("cdn", 10 * 1024 * 1024)
        large = estimate_seconds("cdn", 10 * 1024 * 1024 * 1024)
        self.assertLessEqual(small.low_seconds, small.likely_seconds)
        self.assertLessEqual(small.likely_seconds, small.high_seconds)
        self.assertGreater(large.likely_seconds, small.likely_seconds)

    def test_observed_throughput_is_used(self):
        estimate = estimate_seconds("origin", 1_000_000_000, observed_bytes_per_second=10_000_000)
        self.assertEqual(estimate.likely_seconds, 100)


if __name__ == "__main__":
    unittest.main()