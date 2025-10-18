# backend/app/auth_google.py
import os, jwt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from jwt import PyJWKClient

from .auth_internal import issue_access_token, issue_refresh_token
from .identity import map_idp_claims_to_user
from .db_handle import db

GOOGLE_ISS  = os.getenv("GOOGLE_ISS", "https://accounts.google.com")
GOOGLE_JWKS = os.getenv("GOOGLE_JWKS_URI", "https://www.googleapis.com/oauth2/v3/certs")

router = APIRouter(tags=["auth"])
_jwks = PyJWKClient(GOOGLE_JWKS)  # caches keys internally

class GoogleExchangeBody(BaseModel):
    id_token: str

@router.post("/auth/google/exchange")
def google_exchange(body: GoogleExchangeBody):
    # Read at call time so tests can set env after import
    google_aud = (os.getenv("GOOGLE_AUDIENCE") or "").strip()
    if not google_aud:
        raise HTTPException(500, "Google audience not configured")

    idt = body.id_token
    try:
        # (Optional) fast-fail on unexpected alg
        hdr = jwt.get_unverified_header(idt)
        if hdr.get("alg") != "RS256":
            raise HTTPException(status_code=401, detail=f"unexpected alg: {hdr.get('alg')}")

        key = _jwks.get_signing_key_from_jwt(idt).key
        claims = jwt.decode(
            idt,
            key=key,
            algorithms=["RS256"],
            audience=google_aud,
            issuer=GOOGLE_ISS,
            options={"require": ["exp", "iss", "aud"]},
            leeway=120,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="google id_token expired")
    except jwt.PyJWTError as ex:
        raise HTTPException(status_code=401, detail=f"invalid google id_token: {ex}")

    # Map (iss, sub, email) -> local user (JIT provision if first time)
    user = map_idp_claims_to_user(db, claims)

    # Issue your internal tokens for future calls
    access  = issue_access_token(
        sub=user["id"],
        scope="series:read analyze:run",
        extra={"auth_time": claims.get("auth_time", claims.get("iat"))},
    )
    refresh = issue_refresh_token(sub=user["id"])

    # Optional metadata for clients
    access_ttl  = int(os.getenv("JWT_ACCESS_TTL_SEC", "900"))
    refresh_ttl = int(os.getenv("JWT_REFRESH_TTL_SEC", "2592000"))

    return {
        "ok": True,
        "user": {"id": user["id"], "email": user.get("email")},
        "token_type": "Bearer",
        "access_token": access,
        "expires_in": access_ttl,
        "refresh_token": refresh,
        "refresh_expires_in": refresh_ttl,
    }
