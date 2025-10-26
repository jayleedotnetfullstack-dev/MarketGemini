# app/auth/oidc.py
from __future__ import annotations

import os
import json
import base64
from functools import lru_cache
from typing import List, Dict, Optional

import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Header, status

# Import internal HS256 verifier for hybrid flow
from marketgemini_backend.app.auth.internal import verify_bearer as verify_internal_bearer

# ------------------------
# Environment & flags
# ------------------------
TEST_MODE: bool = os.getenv("TEST_MODE", "").lower() in ("1", "true", "yes", "on")

# ---- Apple env ----
APPLE_ISS: str = os.getenv("APPLE_ISS", "https://appleid.apple.com")
APPLE_JWKS_URI: str = os.getenv("APPLE_JWKS_URI", "https://appleid.apple.com/auth/keys")
APPLE_AUD: str = os.getenv("APPLE_AUDIENCE", "").strip()  # Services ID (web) or Bundle ID (iOS)

# ---- Google env ----
GOOGLE_ISS: str = os.getenv("GOOGLE_ISS", "https://accounts.google.com")
GOOGLE_JWKS_URI: str = os.getenv("GOOGLE_JWKS_URI", "https://www.googleapis.com/oauth2/v3/certs")
GOOGLE_AUD: str = os.getenv("GOOGLE_AUDIENCE", "").strip()  # OAuth client id

# ------------------------
# Helpers
# ------------------------
def _decode_without_sig(jwt_str: str) -> Dict:
    """
    TEST helper: decode payload w/o verifying signature.
    Safer behavior: for tests only; production uses JWKS verification.
    """
    try:
        return jwt.decode(jwt_str, options={"verify_signature": False, "verify_aud": False})
    except jwt.PyJWTError:
        # best-effort base64url decode of payload for debugging
        parts = jwt_str.split(".")
        if len(parts) >= 2:
            p = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
            try:
                return json.loads(base64.urlsafe_b64decode(p.encode("ascii")))
            except Exception:
                return {}
        return {}

# ------------------------
# Core OIDC verifiers
# ------------------------
class OIDCVerifier:
    """
    Verifies an OIDC ID token for a single issuer using its JWKS endpoint.
    """
    def __init__(self, iss: str, jwks_uri: str, audiences: List[str] | str, algs=("RS256",)):
        self.iss = iss
        self._jwk = PyJWKClient(jwks_uri)
        self.algs = list(algs)
        self.audiences = audiences if isinstance(audiences, list) else [audiences]

    def verify(self, token: str) -> Dict:
        # Get correct signing key based on token header (kid)
        key = self._jwk.get_signing_key_from_jwt(token).key
        # Validate signature + claims (iss/aud/exp)
        claims = jwt.decode(
            token,
            key=key,
            algorithms=self.algs,
            audience=self.audiences,
            issuer=self.iss,
            options={"require": ["exp", "iss", "aud"]},
            leeway=120,
        )
        return claims

class MultiIssuerVerifier:
    """
    Chooses the right verifier based on the token's 'iss' claim, then verifies.
    """
    def __init__(self, verifiers: List[OIDCVerifier]):
        self._by_iss: Dict[str, OIDCVerifier] = {v.iss: v for v in verifiers}

    def verify(self, token: str) -> Dict:
        # Peek unverified payload to route by 'iss' (we re-verify immediately after)
        hdrless = jwt.decode(token, options={"verify_signature": False})
        iss = hdrless.get("iss")
        v = self._by_iss.get(iss)
        if not v:
            raise HTTPException(status_code=401, detail=f"untrusted issuer: {iss}")
        return v.verify(token)

# ------------------------
# Builder from env (cached)
# ------------------------
@lru_cache(maxsize=1)
def get_multi_verifier() -> MultiIssuerVerifier:
    """
    Build a multi-issuer verifier from environment configuration.

    Enable a provider by setting its AUDIENCE:
      - APPLE_AUDIENCE = com.yourco.marketgemini.web  (Services ID)  OR an iOS Bundle ID
      - GOOGLE_AUDIENCE = 12345-abc.apps.googleusercontent.com       (OAuth client id)
    """
    verifiers: List[OIDCVerifier] = []

    if APPLE_AUD:
        verifiers.append(
            OIDCVerifier(
                iss=APPLE_ISS,
                jwks_uri=APPLE_JWKS_URI,
                audiences=[APPLE_AUD],
                algs=("RS256",),
            )
        )

    if GOOGLE_AUD:
        verifiers.append(
            OIDCVerifier(
                iss=GOOGLE_ISS,
                jwks_uri=GOOGLE_JWKS_URI,
                audiences=[GOOGLE_AUD],
                algs=("RS256",),
            )
        )

    if not verifiers:
        # Help during config
        raise RuntimeError(
            "No OIDC providers configured. "
            "Set APPLE_AUDIENCE and/or GOOGLE_AUDIENCE in your environment."
        )

    return MultiIssuerVerifier(verifiers)

# ------------------------
# Public helpers
# ------------------------
def verify_oidc_id_token(id_token: str) -> Dict:
    """
    Provider-agnostic OIDC ID-token verification across configured issuers.
    - In TEST_MODE: skip signature verification (still sanity-checkable downstream).
    - In PROD: use JWKS signature verification and strict iss/aud/exp checks.
    """
    if TEST_MODE:
        claims = _decode_without_sig(id_token)
        if not claims:
            raise HTTPException(status_code=401, detail="invalid id_token (test decode failed)")
        iss = claims.get("iss")
        if iss not in ("https://accounts.google.com", "accounts.google.com", APPLE_ISS):
            # allow adding more issuers if you configure them
            raise HTTPException(status_code=401, detail=f"invalid id_token: unexpected iss={iss}")
        return claims

    try:
        verifier = get_multi_verifier()
        claims = verifier.verify(id_token)
        # Additional sanity check for Google 'iss' variants
        iss = claims.get("iss")
        if iss == "accounts.google.com":
            # Accept both canonical forms—already verified above
            pass
        return claims
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="invalid id_token: exp (expired)")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=401, detail="invalid id_token: audience mismatch")
    except jwt.InvalidIssuerError:
        raise HTTPException(status_code=401, detail="invalid id_token: issuer mismatch")
    except jwt.PyJWTError as ex:
        raise HTTPException(status_code=401, detail=f"invalid id_token: {ex}")
    except Exception as ex:
        raise HTTPException(status_code=401, detail=f"invalid id_token: {ex}")

# ------------------------
# Hybrid bearer dependency (internal HS256 first, OIDC fallback)
# ------------------------
async def verify_bearer_hybrid(
    authorization: Optional[str] = Header(None),
    required_scope: Optional[str] = None,
    allow_raw_oidc_without_scope: bool = False,
) -> Dict:
    """
    Route-layer helper:
      1) Try INTERNAL HS256 first (scoped access token).
         - On 403 (insufficient scope), DO NOT fall back to OIDC.
      2) Only on 401 from internal verification, try raw OIDC ID token.
         - Raw OIDC tokens usually don't carry your custom "scope".
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")

    # 1) INTERNAL HS256 first
    try:
        claims = verify_internal_bearer(token, required_scope=None)
        # Enforce required scope for internal tokens
        if required_scope:
            scopes = set((claims.get("scope") or "").split())
            if required_scope not in scopes:
                # IMPORTANT: raise 403 and DO NOT fall back to OIDC
                raise HTTPException(status_code=403, detail="insufficient_scope")
        return claims

    except HTTPException as ex:
        # Only fall back on 401 (invalid/expired/malformed). Propagate others (e.g., 403)
        if ex.status_code != 401:
            raise

    # 2) OIDC fallback (raw ID token)
    claims = verify_oidc_id_token(token)

    # Raw OIDC tokens typically lack your custom scopes. Enforce policy:
    if required_scope and not allow_raw_oidc_without_scope:
        raise HTTPException(
            status_code=403,
            detail="insufficient_scope (use OIDC exchange/callback to obtain scoped access token)",
        )
    return claims

def require_scope_hybrid(required: Optional[str], *, allow_raw_oidc_without_scope: bool = False):
    """
    FastAPI dependency that accepts:
      - internal HS256 access tokens with required scope, or
      - raw OIDC ID tokens (Google/Apple) if allowed explicitly.
    """
    async def dep(authorization: Optional[str] = Header(None)):
        return await verify_bearer_hybrid(
            authorization=authorization,
            required_scope=required,
            allow_raw_oidc_without_scope=allow_raw_oidc_without_scope,
        )
    return dep
