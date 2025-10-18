from typing import List, Optional
def sma(values: List[float], window: int) -> List[Optional[float]]:
    out = []
    s = 0.0
    q: List[float] = []
    for v in values:
        q.append(v)
        s += v
        if len(q) > window:
            s -= q.pop(0)
        out.append(s / len(q))
    return out
