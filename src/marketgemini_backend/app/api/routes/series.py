# src/marketgemini_backend/app/api/routes/series.py
from __future__ import annotations

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

# ✅ Security selector + services
from marketgemini_backend.app.security.base import auth_required
from marketgemini_backend.app.services.series import load_series
from marketgemini_backend.app.services.timeseries import sma
from marketgemini_backend.app.services.detect import robust_zscore

from marketgemini_backend.app.auth.deps import require_scope

router = APIRouter(
    prefix="/v1",
    tags=["series"],
    dependencies=[Depends(require_scope("series:read"))],  # ✅ require HS256/Google token with this scope
)

@router.get("/series")
async def get_series(
    asset: str = Query(..., description="Asset symbol. MVP supports GOLD only."),
    include_indicators: Optional[str] = Query(
        None,
        description="Comma-separated indicators to include (e.g., 'sma_50,sma_200').",
    ),
    # 🔹 NEW anomaly knobs (optional)
    anomaly: bool = Query(
        False,
        description="If true, include robust z-score results (scores + flags) for the series.",
    ),
    anomaly_window: int = Query(
        30, ge=5, le=5000, description="Rolling window for robust z-score."
    ),
    anomaly_threshold: float = Query(
        3.5, gt=0, description="|z| above this is flagged as anomaly."
    ),
    _claims=Depends(auth_required("series:read")),
) -> Dict[str, Any]:
    """
    Protected endpoint requiring scope: series:read

    Auth path is selected by AUTH_MODE:
      - HS256       : internal HS256 access tokens only
      - OIDC       : internal first; fallback to raw OIDC ID token on 401 (raw OIDC lacks custom scopes)
      - OIDC_DIRECT: same as OIDC, but allows raw OIDC even when scope is required
    """
    if asset.upper() != "GOLD":
        raise HTTPException(status_code=400, detail="MVP supports GOLD only")

    series, meta = load_series("gold")
    resp: Dict[str, Any] = {"asset": "GOLD", "series": series, "meta": meta}

    closes = [float(v) for _, v in series]

    # Indicators
    if include_indicators:
        want = {w.strip().lower() for w in include_indicators.split(",") if w.strip()}
        inds: Dict[str, List[float]] = {}
        if "sma_50" in want:
            inds["sma_50"] = sma(closes, 50)
        if "sma_200" in want:
            inds["sma_200"] = sma(closes, 200)
        if inds:
            resp["indicators"] = inds

    # 🔹 Optional anomalies
    if anomaly:
        det = robust_zscore(closes, window=anomaly_window, threshold=anomaly_threshold)
        resp["anomalies"] = {
            "window": anomaly_window,
            "threshold": anomaly_threshold,
            "scores": det["scores"],
            "flags": det["anomalies"],
        }

    return resp


class AnalyzeRequest(BaseModel):
    values: List[float] = Field(..., description="Time series values.")
    window: int = Field(30, ge=1, description="Window length for robust z-score.")
    threshold: float = Field(3.5, gt=0, description="Z-score threshold for anomalies.")


@router.post("/analyze")
async def analyze(
    req: AnalyzeRequest,
    _claims=Depends(auth_required("analyze:run")),
) -> Dict[str, Any]:
    """
    Protected endpoint requiring scope: analyze:run
    Behavior follows AUTH_MODE as described above.
    """
    return robust_zscore(req.values, req.window, req.threshold)
