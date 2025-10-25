# app/auth/google.py  (merged + cleaned + tracing)
from __future__ import annotations

import os
import time
import json
import base64
import hashlib
import secrets
from typing import Dict, Any, Optional
from urllib.parse import urlencode
from functools import lru_cache

import httpx
import jwt
from jwt import PyJWKClient
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from itsdangerous import URLSafeSerializer, BadSignature

from marketgemini_backend.app.core.trace import auth_trace  # <-- tracing
from marketgemini_backend.app.auth.internal import issue_access_token, issue_refresh_token
from marketgemini_backend.app.services.identity import map_idp_claims_to_user
from marketgemini_backend.app.services.db import db

# ------------------------
# Environment & constants
# ------------------------
GOOGLE_ISS            = os.getenv("GOOGLE_ISS", "https://accounts.google.com")
GOOGLE_JWKS_URI       = os.getenv("GOOGLE_JWKS_URI", "https://www.googleapis.com/oauth2/v3/certs")
GOOGLE_DISCOVERY      = os.getenv("GOOGLE_DISCOVERY", "https://accounts.google.com/.well-known/openid-configuration")

# Client configuration
GOOGLE_CLIENT_ID      = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET  = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_AUDIENCE       = (os.getenv("GOOGLE_AUDIENCE") or GOOGLE_CLIENT_ID or "").strip()  # single source of truth

# App / routing
OIDC_REDIRECT_URI     = os.getenv("OIDC_REDIRECT_URI", "http://localhost:8000/auth/callback")
BASE_URL              = os.getenv("BASE_URL", "http://localhost:8000")
TEST_MODE             = os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on")
TEST_MODE_ENFORCE_EXP = os.getenv("TEST_MODE_ENFORCE_EXP", "").lower() in ("1", "true", "yes", "on")

# signed cookie for pkce params
SESSION_SECRET        = os.getenv("SESSION_SECRET", "dev-session-secret")  # use a strong secret in real env
SESSION_COOKIE_NAME   = "oidc_pkce"

router = APIRouter(tags=["auth"])

# Cache JWKS client for verification
@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient:
    return PyJWKClient(GOOGLE_JWKS_URI)

# ------------------------
# Helpers
# ------------------------
def _pkce_params() -> Dict[str, str]:
    """Generate PKCE S256 verifier/challenge and CSRF state/nonce."""
    code_verifier  = secrets.token_urlsafe(64)  # ~86 chars
    digest         = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    state          = secrets.token_urlsafe(24)
    nonce          = secrets.token_urlsafe(24)
    return {
        "code_verifier": code_verifier,
        "code_challenge": code_challenge,
        "state": state,
        "nonce": nonce,
    }

def _sign_session(payload: Dict[str, Any]) -> str:
    return URLSafeSerializer(SESSION_SECRET, salt="oidc").dumps(payload)

def _unsign_session(data: str) -> Dict[str, Any]:
    try:
        return URLSafeSerializer(SESSION_SECRET, salt="oidc").loads(data)
    except BadSignature:
        raise HTTPException(status_code=400, detail="invalid session")

async def _discover(client: Optional[httpx.AsyncClient] = None) -> Dict[str, Any]:
    own = client or httpx.AsyncClient(timeout=10)
    try:
        r = await own.get(GOOGLE_DISCOVERY)
        r.raise_for_status()
        return r.json()
    finally:
        if client is None:
            await own.aclose()

def _decode_without_sig(jwt_str: str) -> Dict[str, Any]:
    """Test helper: decode JWT without verifying signature (TEST_MODE only)."""
    try:
        return jwt.decode(jwt_str, options={"verify_signature": False, "verify_aud": False})
    except jwt.PyJWTError:
        # best-effort parse for debugging
        parts = jwt_str.split(".")
        if len(parts) >= 2:
            p = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            try:
                return json.loads(base64.urlsafe_b64decode(p.encode("ascii")))
            except Exception:
                return {}
        return {}

# ------------------------
# Unified Google ID token verification (RS256)
# ------------------------
async def verify_google_id_token(id_token: str, *, audience: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify a raw Google ID token (RS256) using JWKS.
    Validates signature, aud, iss, and standard time claims.
    In TEST_MODE, signature verification is skipped to simplify mocking.
    """
    aud = (audience or GOOGLE_AUDIENCE or "").strip()
    if not aud:
        raise HTTPException(status_code=500, detail="server misconfigured: GOOGLE_AUDIENCE/GOOGLE_CLIENT_ID missing")

    mode = "TEST" if TEST_MODE else "LIVE"
    auth_trace("oidc.verify.begin", mode=mode, want_aud=aud)

    if TEST_MODE:
        # Skip crypto for test; still basic sanity checks below
        claims = _decode_without_sig(id_token)
        if not claims:
            raise HTTPException(status_code=401, detail="invalid google id_token (test decode failed)")
    else:
        try:
            hdr = jwt.get_unverified_header(id_token)
            if hdr.get("alg") != "RS256":
                raise HTTPException(status_code=401, detail=f"unexpected alg: {hdr.get('alg')}")
            key = _jwks_client().get_signing_key_from_jwt(id_token).key
            claims = jwt.decode(
                id_token,
                key=key,
                algorithms=["RS256"],
                audience=aud,
                issuer=GOOGLE_ISS,
                options={"require": ["exp", "aud", "iss"]},
                leeway=120,
            )
        except jwt.ExpiredSignatureError:
            auth_trace("oidc.verify.expired", mode=mode)
            raise HTTPException(status_code=401, detail="invalid google id_token: exp (expired)")
        except jwt.InvalidAudienceError:
            auth_trace("oidc.verify.aud_mismatch", mode=mode)
            raise HTTPException(status_code=401, detail=f"invalid google id_token: audience mismatch (want={aud})")
        except jwt.InvalidIssuerError:
            auth_trace("oidc.verify.iss_mismatch", mode=mode)
            raise HTTPException(status_code=401, detail=f"invalid google id_token: issuer mismatch (want={GOOGLE_ISS})")
        except jwt.PyJWTError as ex:
            auth_trace("oidc.verify.jwt_error", mode=mode, err=str(ex))
            raise HTTPException(status_code=401, detail=f"invalid google id_token: {ex}")

    iss = claims.get("iss")
    if iss not in ("https://accounts.google.com", "accounts.google.com"):
        auth_trace("oidc.verify.bad_iss_value", mode=mode, iss=iss)
        raise HTTPException(status_code=401, detail="invalid google id_token: iss not Google")

    # TEST_MODE: do not fail on audience mismatch, but trace it
    if TEST_MODE:
        token_aud = claims.get("aud")
        if token_aud and token_aud != aud:
            auth_trace("oidc.verify.test_aud_ignored", token_aud=token_aud, want_aud=aud)

        # Optional strictness: enforce exp in TEST_MODE if requested
        if TEST_MODE_ENFORCE_EXP:
            exp = claims.get("exp")
            now = int(time.time())
            if not isinstance(exp, int) or exp < now:
                auth_trace("oidc.verify.test_exp_enforced", exp=exp, now=now)
                raise HTTPException(status_code=401, detail="google id_token expired (TEST_MODE_ENFORCE_EXP)")

    auth_trace("oidc.verify.ok", mode=mode, aud=claims.get("aud"), iss=iss, exp=claims.get("exp"))
    return claims

# ------------------------
# /auth/login (PKCE start)
# ------------------------
@router.get("/auth/login")
async def auth_login(_: Request):
    """
    Create PKCE S256 params, set them in a signed cookie, and redirect to Google authorization endpoint.
    """
    if not GOOGLE_CLIENT_ID or not OIDC_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="OIDC not configured")

    disc = await _discover()
    auth_ep = disc.get("authorization_endpoint")
    if not auth_ep:
        raise HTTPException(status_code=500, detail="discovery missing authorization_endpoint")

    pkce = _pkce_params()
    cookie = _sign_session({"ts": int(time.time()), **pkce})
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": OIDC_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "code_challenge": pkce["code_challenge"],
        "code_challenge_method": "S256",
        "state": pkce["state"],
        "nonce": pkce["nonce"],
        # optional:
        "access_type": "offline",  # request refresh_token
        "prompt": "consent",       # force prompt to ensure refresh_token first time
    }
    url = f"{auth_ep}?{urlencode(params)}"

    auth_trace("oidc.pkce.start",
               mode="TEST" if TEST_MODE else "LIVE",
               client_id_set=bool(GOOGLE_CLIENT_ID), redirect=OIDC_REDIRECT_URI)

    resp = RedirectResponse(url, status_code=302)
    resp.set_cookie(
        SESSION_COOKIE_NAME,
        cookie,
        secure=False,  # set True in prod with https
        httponly=True,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return resp

# ------------------------
# /auth/callback (PKCE end)
# ------------------------
@router.get("/auth/callback")
async def auth_callback(request: Request, code: str = "", state: str = ""):
    if not code or not state:
        raise HTTPException(status_code=400, detail="missing code/state")

    raw = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw:
        raise HTTPException(status_code=400, detail="missing session")
    sess = _unsign_session(raw)

    if state != sess.get("state"):
        raise HTTPException(status_code=401, detail="state mismatch")

    disc = await _discover()
    token_ep = disc.get("token_endpoint")
    if not token_ep:
        raise HTTPException(status_code=500, detail="discovery missing token_endpoint")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": OIDC_REDIRECT_URI,
        "code_verifier": sess["code_verifier"],
    }

    async with httpx.AsyncClient(timeout=15) as client:
        tr = await client.post(token_ep, data=data, headers={"Accept": "application/json"})
    if tr.status_code != 200:
        auth_trace("oidc.pkce.callback.exchange_failed", status=tr.status_code)
        raise HTTPException(status_code=401, detail=f"token exchange failed: {tr.status_code} {tr.text}")

    tok = tr.json()
    id_token = tok.get("id_token")
    if not id_token:
        raise HTTPException(status_code=401, detail="no id_token in token response")

    # --- Verify the Google ID token via unified helper ---
    claims = await verify_google_id_token(id_token, audience=GOOGLE_AUDIENCE)
    auth_trace("oidc.pkce.callback.verified",
               mode="TEST" if TEST_MODE else "LIVE",
               aud=claims.get("aud"), iss=claims.get("iss"), exp=claims.get("exp"))

    # --- Map to local user and mint INTERNAL tokens ---
    user = map_idp_claims_to_user(db, claims)
    access  = issue_access_token(
        sub=user["id"],
        scope="series:read analyze:run",
        extra={"auth_time": claims.get("auth_time", claims.get("iat"))},
    )
    refresh = issue_refresh_token(sub=user["id"])

    access_ttl  = int(os.getenv("JWT_ACCESS_TTL_SEC", "900"))
    refresh_ttl = int(os.getenv("JWT_REFRESH_TTL_SEC", "2592000"))

    auth_trace("internal.issued_from_oidc",
               sub=user["id"], scopes="series:read analyze:run",
               access_ttl=access_ttl, refresh_ttl=refresh_ttl)

    # clear cookie after success
    resp = Response(
        content=json.dumps({
            "ok": True,
            "user": {"id": user["id"], "email": user.get("email")},
            "token_type": "Bearer",
            "access_token": access,
            "expires_in": access_ttl,
            "refresh_token": refresh,
            "refresh_expires_in": refresh_ttl,
        }),
        media_type="application/json",
        status_code=200,
    )
    resp.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return resp

# ------------------------
# /auth/google/exchange (non-PKCE flow; accepts raw id_token)
# ------------------------
class GoogleExchangeBody(BaseModel):
    id_token: str

@router.post("/auth/google/exchange")
def google_exchange(body: GoogleExchangeBody):
    if not GOOGLE_AUDIENCE:
        raise HTTPException(500, "Google audience not configured")

    idt = body.id_token
    mode = "TEST" if TEST_MODE else "LIVE"
    auth_trace("oidc.exchange.begin", mode=mode)

    try:
        jwks = _jwks_client()
        if TEST_MODE:
            claims = _decode_without_sig(idt)
            token_aud = claims.get("aud")
            if token_aud and token_aud != GOOGLE_AUDIENCE:
                auth_trace("oidc.exchange.test_aud_ignored", token_aud=token_aud, want_aud=GOOGLE_AUDIENCE)

            if TEST_MODE_ENFORCE_EXP:
                exp = claims.get("exp")
                now = int(time.time())
                if not isinstance(exp, int) or exp < now:
                    auth_trace("oidc.exchange.test_exp_enforced", exp=exp, now=now)
                    raise HTTPException(status_code=401, detail="google id_token expired (TEST_MODE_ENFORCE_EXP)")
        else:
            hdr = jwt.get_unverified_header(idt)
            if hdr.get("alg") != "RS256":
                raise HTTPException(status_code=401, detail=f"unexpected alg: {hdr.get('alg')}")
            key = jwks.get_signing_key_from_jwt(idt).key
            claims = jwt.decode(
                idt,
                key=key,
                algorithms=["RS256"],
                audience=GOOGLE_AUDIENCE,
                issuer=GOOGLE_ISS,
                options={"require": ["exp", "iss", "aud"]},
                leeway=120,
            )
    except jwt.ExpiredSignatureError:
        auth_trace("oidc.exchange.expired", mode=mode)
        raise HTTPException(status_code=401, detail="google id_token expired")
    except jwt.PyJWTError as ex:
        auth_trace("oidc.exchange.jwt_error", mode=mode, err=str(ex))
        raise HTTPException(status_code=401, detail=f"invalid google id_token: {ex}")

    auth_trace("oidc.exchange.verified",
               mode=mode, aud=claims.get("aud"), iss=claims.get("iss"), exp=claims.get("exp"))

    # --- Map to local user and mint INTERNAL tokens ---
    user = map_idp_claims_to_user(db, claims)
    access = issue_access_token(
        sub=user["id"],
        scope="series:read analyze:run",
        extra={"auth_time": claims.get("auth_time", claims.get("iat"))},
    )
    refresh = issue_refresh_token(sub=user["id"])

    access_ttl = int(os.getenv("JWT_ACCESS_TTL_SEC", "900"))
    refresh_ttl = int(os.getenv("JWT_REFRESH_TTL_SEC", "2592000"))

    auth_trace("internal.issued_from_oidc",
               sub=user["id"], scopes="series:read analyze:run",
               access_ttl=access_ttl, refresh_ttl=refresh_ttl)

    return {
        "ok": True,
        "user": {"id": user["id"], "email": user.get("email")},
        "token_type": "Bearer",
        "access_token": access,
        "expires_in": access_ttl,
        "refresh_token": refresh,
        "refresh_expires_in": refresh_ttl,
    }
