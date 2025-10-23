# app/auth.py
from __future__ import annotations

import os
import time
import json
import base64
import typing as t

import httpx
import jwt  # PyJWT
from fastapi import HTTPException, Header, status
from dotenv import load_dotenv

load_dotenv()

# =========================
# Internal HS256 token config
# =========================
JWT_SECRET = os.getenv("JWT_SECRET", "dev_secret_do_not_use_in_prod")
JWT_ISS    = os.getenv("JWT_ISS", "marketgemini")
JWT_AUD    = os.getenv("JWT_AUD", "marketgemini-api")
ALGO       = "HS256"

def make_dev_token(
    sub: str = "dev-user",
    ttl_sec: int = 900,
    scope: str = "series:read analyze:run"
) -> str:
    now = int(time.time())
    payload = {
        "sub": sub,
        "iss": JWT_ISS,
        "aud": JWT_AUD,
        "iat": now,
        "nbf": now,
        "exp": now + ttl_sec,
        "scope": scope,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGO)

def verify_bearer(token: str, required_scope: str | None = None) -> dict:
    """
    Verify an INTERNAL HS256 access token (what your /auth/google/exchange mints).
    Enforces issuer/audience/signature/expiry and optional scope.
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

# =========================
# Google OIDC (RS256) config
# =========================
GOOGLE_ISS      = os.getenv("GOOGLE_ISS", "https://accounts.google.com")
GOOGLE_JWKS_URI = os.getenv("GOOGLE_JWKS_URI", "https://www.googleapis.com/oauth2/v3/certs")
GOOGLE_AUD      = os.getenv("GOOGLE_AUDIENCE", "")

def _jwt_header(token: str) -> dict:
    try:
        h = token.split(".")[0]
        # pad for base64
        padded = h + "==="  # safe padding
        return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
    except Exception:
        return {}

async def _verify_google_oidc_rs256(token: str) -> dict:
    """
    Verify a raw Google ID token (RS256) using JWKS.
    Validates signature, aud, iss, and standard time claims.
    """
    header = _jwt_header(token)
    kid = header.get("kid")

    async with httpx.AsyncClient(timeout=10) as client:
        jwks = (await client.get(GOOGLE_JWKS_URI)).json()

    key = None
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(k))
            break
    if key is None:
        raise HTTPException(status_code=401, detail="jwks key not found for kid")

    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=GOOGLE_AUD,
            options={"require": ["exp", "aud"]},
        )
    except jwt.PyJWTError as ex:
        raise HTTPException(status_code=401, detail=f"invalid google id_token: {ex}")

    iss = claims.get("iss")
    if iss not in ("https://accounts.google.com", "accounts.google.com"):
        raise HTTPException(status_code=401, detail="invalid issuer for google id_token")
    return claims

# =========================
# Hybrid verifier for routes
# =========================
# app/auth.py (replace your current hybrid + require_scope with this)

async def verify_bearer_hybrid(
    authorization: t.Optional[str] = Header(None),
    required_scope: str | None = None,
    allow_raw_google_without_scope: bool = False,
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]

    # 1) Try INTERNAL HS256 first
    try:
        # verify signature/iss/aud/exp (no scope here)
        claims = verify_bearer(token, required_scope=None)
        # scope enforcement for internal tokens
        if required_scope:
            scopes = set((claims.get("scope") or "").split())
            if required_scope not in scopes:
                # IMPORTANT: raise 403 and DO NOT fall back to OIDC
                raise HTTPException(status_code=403, detail="insufficient_scope")
        return claims

    except HTTPException as ex:
        # If it's NOT a 401 from HS256 verification, re-raise (e.g., 403 should propagate)
        if ex.status_code != 401:
            raise

        # 2) Only on HS256 401 do we try OIDC fallback (raw Google ID token)
        claims = await _verify_google_oidc_rs256(token)

        # Raw Google ID tokens won't have your custom scopes; enforce policy
        if required_scope and not allow_raw_google_without_scope:
            raise HTTPException(
                status_code=403,
                detail="insufficient_scope (use /auth/google/exchange to obtain scoped access token)",
            )
        return claims


def require_scope(required: str, *, allow_raw_google_without_scope: bool = False):
    async def dep(authorization: t.Optional[str] = Header(None)):
        return await verify_bearer_hybrid(
            authorization=authorization,
            required_scope=required,
            allow_raw_google_without_scope=allow_raw_google_without_scope,
        )
    return dep


