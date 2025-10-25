# src/marketgemini_backend/app/security/base.py
from __future__ import annotations

import os
from typing import Optional
from fastapi import HTTPException

# Internal HS256-only dependency
from marketgemini_backend.app.auth.internal import require_scope as require_scope_internal

# ✅ Hybrid (HS256 first, fallback to raw OIDC ID token on 401)
#    Correct module path is security.oidc (not auth.oidc)
from marketgemini_backend.app.security.oidc import require_scope_hybrid

from marketgemini_backend.app.core.trace import auth_trace


def _auth_mode() -> str:
    """
    AUTH_MODE:
      - HS256       : accept only internal HS256 access tokens (scoped)
      - OIDC        : hybrid; disallow raw OIDC when scope required
      - OIDC_DIRECT : hybrid; allow raw OIDC even when scope required
    """
    return (os.getenv("AUTH_MODE", "HS256") or "").strip().upper()


def auth_required(required_scope: Optional[str] = None):
    """
    Route-level dependency selector.

    Example usage:
      from marketgemini_backend.app.security.base import auth_required
      @router.get("/series")
      def list_series(_claims = Depends(auth_required("series:read"))):
          ...

    Returns a FastAPI dependency callable.
    """
    mode = _auth_mode()
    auth_trace("security.selector", mode=mode, required_scope=required_scope)

    if mode == "HS256":
        return require_scope_internal(required_scope)

    elif mode == "OIDC":
        # Hybrid: try INTERNAL first; if that returns 401, fall back to OIDC.
        # Raw OIDC tokens WITHOUT scopes will be rejected when a scope is required.
        return require_scope_hybrid(required_scope, allow_raw_oidc_without_scope=False)

    elif mode == "OIDC_DIRECT":
        # Hybrid: same as above, but ALLOW raw OIDC even when a scope is required.
        # (Use when you want to treat Google ID tokens as sufficient on scoped routes.)
        return require_scope_hybrid(required_scope, allow_raw_oidc_without_scope=True)

    raise HTTPException(status_code=500, detail=f"Unsupported AUTH_MODE: {mode}")
