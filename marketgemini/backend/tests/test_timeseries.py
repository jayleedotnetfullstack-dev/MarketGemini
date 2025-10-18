# backend/tests/test_timeseries.py
from app.timeseries import sma

def test_sma_window_3():
    vals = [1, 2, 3, 4, 5]
    out = sma(vals, 3)
    # last average of [3,4,5] = 4.0
    assert round(out[-1], 5) == 4.0

def test_sma_monotonic_increasing():
    vals = [10, 20, 30, 40, 50]
    out = sma(vals, 2)
    assert out[1] == 15.0  # (10+20)/2
    assert out[2] == 25.0  # (20+30)/2

def test_sma_window_larger_than_series():
    vals = [5, 5]
    out = sma(vals, 5)
    # our implementation averages over current available length
    assert out == [5.0, 5.0]
