import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.timeseries import sma  # noqa: E402

class TimeseriesTests(unittest.TestCase):
    def test_sma_window_3(self):
        vals = [1, 2, 3, 4, 5]
        out = sma(vals, 3)
        self.assertAlmostEqual(out[-1], 4.0, places=5)  # avg of [3,4,5]

    def test_sma_monotonic_increasing(self):
        vals = [10, 20, 30, 40, 50]
        out = sma(vals, 2)
        self.assertEqual(out[1], 15.0)  # (10+20)/2
        self.assertEqual(out[2], 25.0)  # (20+30)/2

    def test_sma_window_larger_than_series(self):
        vals = [5, 5]
        out = sma(vals, 5)
        self.assertEqual(out, [5.0, 5.0])

if __name__ == "__main__":
    unittest.main()