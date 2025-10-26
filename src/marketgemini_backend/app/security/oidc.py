# src/marketgemini_backend/app/security/oidc.py
from __future__ import annotations
from typing import Optional

from fastapi import Header, HTTPException, status

from marketgemini_backend.app.core.trace import auth_trace

# Internal HS256 verification (returns claims or raises HTTPException(401/403/...))
from marketgemini_backend.app.auth.internal import verify_bearer as _verify_internal

# Google OIDC verification helper (async)
from marketgemini_backend.app.auth.google import verify_google_id_token as _verify_google


# --------------------------------------------------------------------------------------
# Hybrid OIDC dependency:
#   1) Try INTERNAL HS256 first (enforce scope here).
#   2) Only on INTERNAL 401, try OIDC ID token.
#   3) If scope is required and allow_raw_oidc_without_scope is False => reject raw OIDC.
# --------------------------------------------------------------------------------------
def require_scope_hybrid(required_scope: Optional[str] = None, *, allow_raw_oidc_without_scope: bool = False):
    """
    Hybrid dependency for routes that should accept internal tokens and (optionally)
    raw Google ID tokens.

    - If INTERNAL verify passes but scope missing -> 403 (do NOT fall back).
    - If INTERNAL verify raises 401 -> fall back to OIDC.
    - For OIDC fallback, by default we reject when a scope is required (since raw ID tokens
      typically don't carry your custom scopes). Set allow_raw_oidc_without_scope=True
      to allow raw OIDC even on scoped routes.
    """
    async def dep(authorization: str = Header(None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
        token = authorization.split(" ", 1)[1].strip()

        # 1) INTERNAL FIRST
        try:
            claims = _verify_internal(token, required_scope=None)
            # enforce scope on internal tokens
            if required_scope:
                scopes = set((claims.get("scope") or "").split())
                if required_scope not in scopes:
                    auth_trace("hybrid.internal.scope_miss", required=required_scope, scopes=list(scopes))
                    # IMPORTANT: do not fall back on scope failure
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_scope")
            auth_trace("hybrid.internal.ok", iss=claims.get("iss"), sub=claims.get("sub"))
            return claims

        except HTTPException as ex:
            # Only fall back on INTERNAL 401
            if ex.status_code != status.HTTP_401_UNAUTHORIZED:
                auth_trace("hybrid.internal.fail_nofallback", code=ex.status_code, detail=str(ex.detail))
                raise
            auth_trace("hybrid.internal.unauthorized_fallback_to_oidc")

        # 2) OIDC FALLBACK
        try:
            claims = await _verify_google(token)  # verifies iss/aud/exp/signature (or test-mode rules)
            if required_scope and not allow_raw_oidc_without_scope:
                auth_trace("hybrid.oidc.no_scopes_denied", required=required_scope)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="insufficient_scope (use /auth/google/exchange to obtain scoped internal access)",
                )
            auth_trace("hybrid.oidc.ok", iss=claims.get("iss"), sub=claims.get("sub"))
            return claims

        except HTTPException as ex:
            auth_trace("hybrid.oidc.fail", code=ex.status_code, detail=str(ex.detail))
            raise

    return dep


# --------------------------------------------------------------------------------------
# Pure OIDC dependency (no HS256). Use when endpoint must accept only IdP tokens.
# --------------------------------------------------------------------------------------
def oidc_idtoken_required(required_scope: Optional[str] = None):
    async def dep(authorization: str = Header(None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
        token = authorization.split(" ", 1)[1].strip()

        try:
            claims = await _verify_google(token)
        except HTTPException as ex:
            auth_trace("oidc.only.fail", code=ex.status_code, detail=str(ex.detail))
            raise

        if required_scope:
            scopes = (claims.get("scope") or claims.get("scp") or "")
            if required_scope not in scopes.split():
                auth_trace("oidc.only.scope_miss", required=required_scope, token_scopes=scopes)
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_scope")

        auth_trace("oidc.only.ok", iss=claims.get("iss"), sub=claims.get("sub"))
        return claims

    return dep


# --------------------------------------------------------------------------------------
# Compatibility wrapper (name used elsewhere)
# --------------------------------------------------------------------------------------
async def verify_oidc_id_token(token: str):
    """
    Backwards-compatible wrapper name that delegates to the Google verifier.
    """
    return await _verify_google(token)


# Backwards-compatible alias used by base.py in older code paths
def oidc_required_hybrid(required_scope: Optional[str] = None, *, allow_raw_oidc_without_scope: bool = False):
    return require_scope_hybrid(required_scope, allow_raw_oidc_without_scope=allow_raw_oidc_without_scope)
