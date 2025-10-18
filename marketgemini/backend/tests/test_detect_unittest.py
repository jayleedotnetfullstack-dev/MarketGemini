import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.detect import robust_zscore  # noqa: E402

class DetectTests(unittest.TestCase):
    def test_anomaly_spike_caught(self):
        values = [1, 1, 1, 10, 1, 1]
        res = robust_zscore(values, window=3, threshold=3.5)
        self.assertEqual(len(res["scores"]), len(values))
        self.assertTrue(any(res["anomalies"]))

    def test_no_anomaly_flat_series(self):
        values = [2, 2, 2, 2, 2]
        res = robust_zscore(values, window=3, threshold=3.5)
        self.assertFalse(any(res["anomalies"]))

    def test_window_autoshrink_when_short_series(self):
        values = [1.0, 100.0]
        res = robust_zscore(values, window=30, threshold=3.5)
        self.assertEqual(len(res["scores"]), 2)

if __name__ == "__main__":
    unittest.main()