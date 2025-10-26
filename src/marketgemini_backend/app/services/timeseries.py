from __future__ import annotations
from typing import List, Optional

def sma(values: List[float], window: int) -> List[Optional[float]]:
    """
    Simple Moving Average (SMA).
    Returns an array the same length as `values`.
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
