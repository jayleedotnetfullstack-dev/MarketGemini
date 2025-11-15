from __future__ import annotations

from typing import List, Dict, Any
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field

from marketgemini_backend.app.security.base import auth_required
from marketgemini_backend.app.services.detect import robust_zscore
from marketgemini_backend.app.services.series import load_series
from marketgemini_backend.app.services.timeseries import sma  # optional, handy later
from marketgemini_backend.app.auth.deps import require_scope

router = APIRouter(
    prefix="/v1",
    tags=["anomaly"],
    dependencies=[Depends(require_scope("analyze:run"))],  # ✅ require analyze scope
)

# ---------- Models ----------

class AnomalyRequest(BaseModel):
    values: List[float] = Field(..., description="Time-series values to analyze.")
    window: int = Field(30, ge=1, description="Window length for robust z-score.")
    threshold: float = Field(3.5, gt=0, description="Z-score threshold for anomalies.")

class AnomalyResult(BaseModel):
    window: int
    threshold: float
    scores: List[float]
    flags: List[bool]

# ---------- Endpoints ----------

@router.get("/anomaly", response_model=AnomalyResult)
async def anomaly_for_asset(
    asset: str = Query(..., description="Asset symbol (MVP: GOLD only)"),
    window: int = Query(30, ge=1, description="Window length for robust z-score."),
    threshold: float = Query(3.5, gt=0, description="Z-score threshold for anomalies."),
    _claims = Depends(auth_required("series:read")),
) -> Dict[str, Any]:
    """
    Compute anomalies for a known asset using server-side series.
    """
    if asset.upper() != "GOLD":
        raise HTTPException(status_code=400, detail="MVP supports GOLD only")

    series, _meta = load_series("gold")
    values = [float(v) for _, v in series]
    out = robust_zscore(values, window=window, threshold=threshold)
    return {
        "window": window,
        "threshold": threshold,
        "scores": out["scores"],
        "flags": out["anomalies"],
    }


@router.post("/anomaly", response_model=AnomalyResult)
async def anomaly_for_payload(
    req: AnomalyRequest,
    _claims = Depends(auth_required("analyze:run")),
) -> Dict[str, Any]:
    """
    Compute anomalies from posted values.
    """
    out = robust_zscore(req.values, window=req.window, threshold=req.threshold)
    return {
        "window": req.window,
        "threshold": req.threshold,
        "scores": out["scores"],
        "flags": out["anomalies"],
    }
