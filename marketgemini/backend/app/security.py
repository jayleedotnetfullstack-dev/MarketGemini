# backend/app/security.py
import os
from typing import Optional
from fastapi import HTTPException

# Hybrid verifier (from app/auth.py)
from .auth import require_scope as _require_scope

# Optional legacy imports (for direct HS256-only or OIDC-only test modes)
try:
    from .security_hs256 import hs256_required
except ImportError:
    hs256_required = None

try:
    from .security_oidc import oidc_required
except ImportError:
    oidc_required = None


def auth_required(required_scope: Optional[str] = None):
    """
    Route-level dependency selector.
    - In AUTH_MODE=OIDC or OIDC_DIRECT: use hybrid verifier (handles internal HS256 + Google ID tokens)
    - In AUTH_MODE=HS256: use HS256-only auth (for pure local dev)
    """
    mode = (os.getenv("AUTH_MODE", "HS256") or "").strip().upper()

    if mode in ("OIDC", "OIDC_DIRECT"):
        # Use the unified hybrid verifier (preferred path)
        return _require_scope(required_scope, allow_raw_google_without_scope=False)

    # HS256 fallback (
