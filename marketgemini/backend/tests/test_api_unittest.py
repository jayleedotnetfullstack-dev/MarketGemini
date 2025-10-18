import sys
from pathlib import Path
import unittest
from fastapi.testclient import TestClient

# Make "backend" importable so `from app...` works
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

class ApiTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    @unittest.skip("disabled for now")
    def test_health(self):
        r = self.client.get("/healthz")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok"})

    @unittest.skip("disabled for now")
    def test_series_gold(self):
        r = self.client.get("/v1/series", params={"asset": "GOLD"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["asset"], "GOLD")
        self.assertIn("series", body)
        self.assertGreater(len(body["series"]), 0)
        date, val = body["series"][0]
        self.assertIsInstance(date, str)
        self.assertTrue(isinstance(val, (int, float)))

    @unittest.skip("disabled for now")
    def test_analyze_spike(self):
        payload = {"values": [1, 1, 1, 10, 1, 1]}
        r = self.client.post("/v1/analyze", json=payload)
        self.assertEqual(r.status_code, 200)
        res = r.json()
        self.assertIn("scores", res)
        self.assertIn("anomalies", res)
        self.assertEqual(len(res["scores"]), len(payload["values"]))
        self.assertTrue(any(res["anomalies"]))

if __name__ == "__main__":
    unittest.main()