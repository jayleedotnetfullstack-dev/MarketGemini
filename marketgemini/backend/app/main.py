# backend/app/main.py
import os
from fastapi import FastAPI
from .security import auth_required  # selector (HS256 dev vs internal in OIDC)

app = FastAPI(title="MarketGemini API", version="0.4.0")

AUTH_MODE = (os.getenv("AUTH_MODE", "HS256") or "").strip().upper()

# 0) Auth routes (login/exchange) - only wire when OIDC-mode is enabled
if AUTH_MODE in ("OIDC", "OIDC_DIRECT"):
    try:
        from .auth_google import router as google_router
        app.include_router(google_router)
    except Exception as ex:
        print(f"[main] Skipping google router: {ex}")

# 1) Health check (open)
@app.get("/healthz")
def health():
    return {"status": "ok"}

# 2) Series and analysis routes
try:
    from .routes_series import router as series_router
    app.include_router(series_router)
except Exception as ex:
    print(f"[main] Skipping routes_series router: {ex}")
