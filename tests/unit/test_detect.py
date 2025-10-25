# backend/tests/test_detect.py
from marketgemini_backend.app.services.detect import robust_zscore

def test_anomaly_spike_caught():
    values = [1, 1, 1, 10, 1, 1]
    res = robust_zscore(values, window=3, threshold=3.5)
    assert len(res["scores"]) == len(values)
    assert any(res["anomalies"])

def test_no_anomaly_flat_series():
    values = [2, 2, 2, 2, 2]
    res = robust_zscore(values, window=3, threshold=3.5)
    assert not any(res["anomalies"])

def test_window_autoshrink_when_short_series():
    values = [1.0, 100.0]
    res = robust_zscore(values, window=30, threshold=3.5)
    # should still return same length
    assert len(res["scores"]) == 2
