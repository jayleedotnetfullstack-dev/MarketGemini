# src/marketgemini_backend/app/services/timeseries.py
from __future__ import annotations
from typing import List, Optional

def sma(values: List[float], window: int) -> List[Optional[float]]:
    """
    Simple Moving Average (SMA) calculator.
    Returns a list of SMA values, aligned with the input length.

    Args:
        values: List of numeric samples.
        window: Window size for averaging.

    Example:
        sma([1, 2, 3, 4, 5], 3) -> [1.0, 1.5, 2.0, 3.0, 4.0]
    """
    out: List[Optional[float]] = []
    s = 0.0
    q: List[float] = []

    for v in values:
        q.append(v)
        s += v
        if len(q) > window:
            s -= q.pop(0)
        out.append(s / len(q))
    return out
