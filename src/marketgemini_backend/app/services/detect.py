from typing import List, Dict, Any
import numpy as np
def robust_zscore(values: List[float], window: int = 30, threshold: float = 3.5) -> Dict[str, Any]:
    arr = np.array(values, dtype=float)
    n = len(arr)
    if n == 0:
        return {"scores": [], "anomalies": []}
    if window > n:
        window = max(8, n // 2 or 1)
    scores: List[float] = []
    anomalies: List[bool] = []
    for i in range(n):
        start = max(0, i - window)
        seg = arr[start : i + 1]
        med = float(np.median(seg))
        mad = float(np.median(np.abs(seg - med))) + 1e-9
        s = 0.6745 * (float(arr[i]) - med) / mad
        scores.append(float(s))
        anomalies.append(abs(s) > threshold)
    return {"scores": scores, "anomalies": anomalies}
