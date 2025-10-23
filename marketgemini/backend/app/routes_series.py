# backend/app/routes_series.py
from __future__ import annotations

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from .series import load_series
from .timeseries import sma
from .detect import robust_zscore
from .auth import require_scope  # hybrid auth dependency (HS256 first, fallback to OIDC)

router = APIRouter(prefix="/v1", tags=["series"])

@router.get("/series")
async def get_series(
    asset: str = Query(..., description="Asset symbol. MVP supports GOLD only."),
    include_indicators: Optional[str] = Query(
        None,
        description="Comma-separated indicators to include (e.g. 'sma_50,sma_200').",
    ),
    _claims = Depends(require_scope("series:read")),
) -> Dict[str, Any]:
    """
    Protected endpoint requiring scope: series:read
    Accepts either your internal HS256 access token or a Google ID token
    (via the hybrid verifier). For scoped access, clients should use your
    internal token obtained from /auth/google/exchange.
    """
    if asset.upper() != "GOLD":
        raise HTTPException(status_code=400, detail="MVP supports GOLD only")

    s, meta = load_series("gold")
    resp: Dict[str, Any] = {"asset": "GOLD", "series": s, "meta": meta}

    if include_indicators:
        want = {w.strip().lower() for w in include_indicators.split(",") if w.strip()}
        closes = [float(v) for _, v in s]
        inds: Dict[str, List[float]] = {}
        if "sma_50" in want:
            inds["sma_50"] = sma(closes, 50)
        if "sma_200" in want:
            inds["sma_200"] = sma(closes, 200)
        if inds:
            resp["indicators"] = inds
    return resp


class AnalyzeRequest(BaseModel):
    values: List[float] = Field(..., description="Time series values.")
    window: int = Field(30, ge=1, description="Window length for robust z-score.")
    threshold: float = Field(3.5, gt=0, description="Z-score threshold for anomalies.")


@router.post("/analyze")
async def analyze(
    req: AnalyzeRequest,
    _claims = Depends(require_scope("analyze:run")),
) -> Dict[str, Any]:
    """
    Protected endpoint requiring scope: analyze:run
    Works with either HS256 (internal) or OIDC (exchanged to internal) tokens.
    """
    return robust_zscore(req.values, req.window, req.threshold)
