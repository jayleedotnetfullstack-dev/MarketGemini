# backend/app/main.py
import os
from fastapi import FastAPI, Depends, Request
from fastapi.openapi.utils import get_openapi
from dotenv import load_dotenv

# Load .env before any auth modules read environment variables
load_dotenv()

from marketgemini_backend.app.core.logging import setup_logging
setup_logging()

from .security.base import auth_required  # selector (HS256 dev vs internal in OIDC)

app = FastAPI(title="MarketGemini API", version="0.4.0")

AUTH_MODE = (os.getenv("AUTH_MODE", "HS256") or "").strip().upper()

# 0) Auth routes (login/exchange) - only wire when OIDC-mode is enabled
if AUTH_MODE in ("OIDC", "OIDC_DIRECT"):
    try:
        from .auth.google import router as google_router
        app.include_router(google_router)
    except Exception as ex:
        print(f"[main] Skipping google router: {ex}")

# 1) Health check (open)
@app.get("/healthz")
def health():
    return {"status": "ok"}

# 1.25) Echo Authorization header (debug)
@app.get("/auth/echo-header", tags=["auth"])
def echo_header(request: Request):
    """
    Debug endpoint: echoes back the Authorization header exactly as received.
    Useful to detect 'Bearer Bearer <token>' or missing token.
    """
    auth_header = request.headers.get("authorization")
    return {
        "received_authorization_header": auth_header,
        "note": "Paste ONLY the raw JWT in Swagger's Authorize dialog; it adds 'Bearer ' for you."
    }

# 1.5) Who am I (debug) - validates token but does not require a specific scope
@app.get("/auth/me", tags=["auth"])
def auth_me(_claims = Depends(auth_required(None))):  # None => just validate; no scope gate
    """
    Return decoded claims of the currently authenticated principal.
    Use Swagger 'Authorize' to paste your internal access token (raw JWT).
    """
    return _claims

# 2) Series and analysis routes
try:
    from .api.routes.series import router as series_router
    app.include_router(series_router)
except Exception as ex:
    print(f"[main] Skipping routes_series router: {ex}")


# --- Swagger/OpenAPI: Add Bearer JWT "Authorize" button ---
def _add_bearer_security_to_openapi(app: FastAPI) -> None:
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=getattr(app, "description", None),
            routes=app.routes,
        )
        # Add security scheme
        components = openapi_schema.setdefault("components", {})
        security_schemes = components.setdefault("securitySchemes", {})
        security_schemes["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "Paste your internal access token minted by /auth/callback.\n"
                "**Do not** include the 'Bearer ' prefix here; Swagger will add it."
            ),
        }

        # Apply BearerAuth to all operations by default (don’t override routes that set security explicitly)
        for path_item in openapi_schema.get("paths", {}).values():
            for op in path_item.values():
                if isinstance(op, dict):
                    op.setdefault("security", [{"BearerAuth": []}])

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

_add_bearer_security_to_openapi(app)
