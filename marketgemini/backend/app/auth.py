# app/auth.py
from __future__ import annotations

import os
import time
import json
import base64
import typing as t
from functools import lru_cache

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
    Verify an INTERNAL HS256 access token (what your OIDC exchange/callback mints).
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
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token: exp (expired)"
        )
    except jwt.InvalidIssuerError as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: issuer mismatch (got={getattr(ex, 'issuer', None)}, want={JWT_ISS})"
        )
    except jwt.InvalidAudienceError as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid token: audience mismatch (want={JWT_AUD})"
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
GOOGLE_ISS          = os.getenv("GOOGLE_ISS", "https://accounts.google.com")
GOOGLE_JWKS_URI     = os.getenv("GOOGLE_JWKS_URI", "https://www.googleapis.com/oauth2/v3/certs")
GOOGLE_AUD          = os.getenv("GOOGLE_AUDIENCE", "")  # must be your web client_id

def _b64url_json(segment: str) -> dict:
    # robust Base64URL decode with correct padding
    pad = (-len(segment)) % 4
    segment = segment + ("=" * pad)
    try:
        return json.loads(base64.urlsafe_b64decode(segment.encode("ascii")))
    except Exception:
        return {}

def _jwt_header(token: str) -> dict:
    parts = token.split(".")
    if len(parts) < 2:
        return {}
    return _b64url_json(parts[0])

@lru_cache(maxsize=1)
def _jwks_cache() -> dict:
    # cached JWKS to avoid network on every call; invalidate by restarting app (fine for dev)
    with httpx.Client(timeout=10) as client:
        r = client.get(GOOGLE_JWKS_URI)
        r.raise_for_status()
        return r.json()

async def _verify_google_oidc_rs256(token: str) -> dict:
    """
    Verify a raw Google ID token (RS256) using JWKS.
    Validates signature, aud, iss, and standard time claims.
    """
    if not GOOGLE_AUD:
        # Misconfiguration: we must know our client_id
        raise HTTPException(status_code=500, detail="server misconfigured: GOOGLE_AUDIENCE missing")

    header = _jwt_header(token)
    kid = header.get("kid")

    jwks = _jwks_cache()
    key = None
    for k in jwks.get("keys", []):
        if k.get("kid") == kid:
            key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(k))
            break
    if key is None:
        # key rotation race; try refetch once
        try:
            _jwks_cache.cache_clear()
            jwks = _jwks_cache()
            for k in jwks.get("keys", []):
                if k.get("kid") == kid:
                    key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(k))
                    break
        except Exception:
            pass
    if key is None:
        raise HTTPException(status_code=401, detail="jwks key not found for kid")

    try:
        claims = jwt.decode(
            token,
            key=key,
            algorithms=["RS256"],
            audience=GOOGLE_AUD,
            issuer=GOOGLE_ISS,
            options={"require": ["exp", "aud", "iss"]},
            leeway=120,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="invalid google id_token: exp (expired)")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=401, detail=f"invalid google id_token: audience mismatch (want={GOOGLE_AUD})")
    except jwt.InvalidIssuerError:
        raise HTTPException(status_code=401, detail=f"invalid google id_token: issuer mismatch (want={GOOGLE_ISS})")
    except jwt.PyJWTError as ex:
        raise HTTPException(status_code=401, detail=f"invalid google id_token: {ex}")

    iss = claims.get("iss")
    if iss not in ("https://accounts.google.com", "accounts.google.com"):
        raise HTTPException(status_code=401, detail="invalid google id_token: iss not Google")
    return claims

# =========================
# Hybrid verifier for routes
# =========================
async def verify_bearer_hybrid(
    authorization: t.Optional[str] = Header(None),
    required_scope: str | None = None,
    allow_raw_google_without_scope: bool = False,
) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    # 1) Try INTERNAL HS256 first
    try:
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
                detail="insufficient_scope (use /auth/google/exchange or /auth/callback to obtain scoped access token)",
            )
        return claims

def require_scope(required: str | None, *, allow_raw_google_without_scope: bool = False):
    async def dep(authorization: t.Optional[str] = Header(None)):
        return await verify_bearer_hybrid(
            authorization=authorization,
            required_scope=required,
            allow_raw_google_without_scope=allow_raw_google_without_scope,
        )
    return dep
