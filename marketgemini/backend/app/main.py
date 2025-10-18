# backend/app/main.py
import os
from fastapi import FastAPI, HTTPException, Query, Depends
from pydantic import BaseModel
from typing import Optional

from .series import load_series
from .timeseries import sma
from .detect import robust_zscore
from .security import auth_required  # selector (HS256 dev vs internal in OIDC)

app = FastAPI(title="MarketGemini API", version="0.4.0")

AUTH_MODE = (os.getenv("AUTH_MODE", "HS256") or "").strip().upper()

# 0) Auth routes (login/exchange) - only wire when OIDC-mode is enabled
if AUTH_MODE in ("OIDC", "OIDC_DIRECT"):
    try:
        from .auth_google import router as google_router
        app.include_router(google_router)
    except Exception as ex:
        # Don’t block HS256/local runs if optional deps/files are missing
        print(f"[main] Skipping google router: {ex}")

# 1) Health - OPEN
@app.get("/healthz")
def health():
    return {"status": "ok"}

# 2) Protected business endpoints (expect YOUR internal token when AUTH_MODE=OIDC)
@app.get("/v1/series", dependencies=[Depends(auth_required("series:read"))])
def series(asset: str = Query(...), include_indicators: Optional[str] = None):
    if asset.upper() != "GOLD":
        raise HTTPException(status_code=400, detail="MVP supports GOLD only")

    s, meta = load_series("gold")
    resp = {"asset": "GOLD", "series": s, "meta": meta}

    if include_indicators:
        want = {w.strip().lower() for w in include_indicators.split(",")}
        closes = [float(v) for _, v in s]
        inds = {}
        if "sma_50" in want:
            inds["sma_50"] = sma(closes, 50)
        if "sma_200" in want:
            inds["sma_200"] = sma(closes, 200)
        if inds:
            resp["indicators"] = inds
    return resp

class AnalyzeRequest(BaseModel):
    values: list[float]
    window: int = 30
    threshold: float = 3.5

@app.post("/v1/analyze", dependencies=[Depends(auth_required("analyze:run"))])
def analyze(req: AnalyzeRequest):
    return robust_zscore(req.values, req.window, req.threshold)
