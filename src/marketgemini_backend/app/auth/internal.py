from __future__ import annotations

import os
import time
import jwt
from typing import Optional, Dict, Any
from fastapi import HTTPException, Header, status  # for API-friendly errors

from marketgemini_backend.app.core.trace import auth_trace

# =========================
# Internal HS256 token config
# =========================
JWT_SECRET = os.getenv("JWT_SECRET", "dev_secret_do_not_use_in_prod")
JWT_ISS    = os.getenv("JWT_ISS", "marketgemini")
JWT_AUD    = os.getenv("JWT_AUD", "marketgemini-api")
ALGO       = "HS256"

ACCESS_TTL  = int(os.getenv("JWT_ACCESS_TTL_SEC", "900"))        # 15m
REFRESH_TTL = int(os.getenv("JWT_REFRESH_TTL_SEC", "2592000"))   # 30d

def _now() -> int:
    return int(time.time())

# -------------------------
# Issuers
# -------------------------
def issue_access_token(
    sub: str,
    scope: str = "series:read analyze:run",
    extra: Optional[Dict[str, Any]] = None,
    ttl: Optional[int] = None,
) -> str:
    now = _now()
    payload: Dict[str, Any] = {
        "iss": JWT_ISS,
        "aud": JWT_AUD,
        "sub": sub,
        "scope": scope,
        "iat": now,
        "nbf": now,
        "exp": now + (ttl or ACCESS_TTL),
    }
    if extra:
        payload.update(extra)

    tok = jwt.encode(payload, JWT_SECRET, algorithm=ALGO)
    auth_trace(
        "internal.issue_access",
        sub=sub,
        scope=scope,
        exp=payload["exp"],
        exp_human=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(payload["exp"])),
    )
    return tok

def issue_refresh_token(sub: str, ttl: Optional[int] = None) -> str:
    now = _now()
    payload: Dict[str, Any] = {
        "iss": JWT_ISS,
        "aud": JWT_AUD,
        "sub": sub,
        "iat": now,
        "nbf": now,
        "exp": now + (ttl or REFRESH_TTL),
        "typ": "refresh",
    }
    tok = jwt.encode(payload, JWT_SECRET, algorithm=ALGO)
    auth_trace(
        "internal.issue_refresh",
        sub=sub,
        exp=payload["exp"],
        exp_human=time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(payload["exp"])),
    )
    return tok

# -------------------------
# Dev helper (kept for tests/local)
# -------------------------
def make_dev_token(
    sub: str = "dev-user",
    ttl_sec: int = 900,
    scope: str = "series:read analyze:run",
) -> str:
    """
    Minimal helper to mint a short-lived dev access token for tests and local runs.
    """
    return issue_access_token(sub=sub, scope=scope, ttl=ttl_sec)

# -------------------------
# Verifiers (programmatic)
# -------------------------
def verify_access(token: str) -> Dict[str, Any]:
    claims = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[ALGO],
        audience=JWT_AUD,
        issuer=JWT_ISS,
        options={"require": ["exp", "iss", "aud"]},
    )
    auth_trace(
        "internal.verify_access_ok",
        sub=claims.get("sub"),
        scope=claims.get("scope"),
        exp=claims.get("exp"),
    )
    return claims

def verify_refresh(token: str) -> Dict[str, Any]:
    claims = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[ALGO],
        audience=JWT_AUD,
        issuer=JWT_ISS,
        options={"require": ["exp", "iss", "aud"]},
    )
    if claims.get("typ") != "refresh":
        raise jwt.InvalidTokenError("not a refresh token")
    auth_trace(
        "internal.verify_refresh_ok",
        sub=claims.get("sub"),
        exp=claims.get("exp"),
    )
    return claims

# -------------------------
# Verifier for FastAPI deps (internal-only)
# -------------------------
def verify_bearer(token: str, required_scope: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify an INTERNAL HS256 access token (what your OIDC exchange/callback mints).
    Enforces issuer/audience/signature/expiry and optional scope.
    Raises FastAPI HTTPException on failure (401/403), matching old behavior.
    """
    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[ALGO],
            audience=JWT_AUD,
            issuer=JWT_ISS,
            options={"require": ["exp", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token: exp (expired)",
        )
    except jwt.InvalidIssuerError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: issuer mismatch (want={JWT_ISS})",
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: audience mismatch (want={JWT_AUD})",
        )
    except jwt.PyJWTError as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: {ex}",
        )

    if required_scope:
        scopes = set((claims.get("scope") or "").split())
        if required_scope not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient_scope",
            )
    return claims

def require_scope(required: Optional[str]):
    """
    FastAPI dependency that ONLY accepts internal HS256 tokens.
    (No Google fallback here—use your google module for that.)
    """
    async def dep(authorization: Optional[str] = Header(None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing token")
        token = authorization.split(" ", 1)[1].strip()
        if not token:
            raise HTTPException(status_code=401, detail="Missing token")
        return verify_bearer(token, required_scope=required)
    return dep
