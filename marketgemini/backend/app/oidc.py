# backend/app/oidc.py
from __future__ import annotations
import os
import jwt
from typing import List, Dict
from jwt import PyJWKClient

# ---- Apple env ----
APPLE_ISS: str = os.getenv("APPLE_ISS", "https://appleid.apple.com")
APPLE_JWKS_URI: str = os.getenv("APPLE_JWKS_URI", "https://appleid.apple.com/auth/keys")
APPLE_AUD: str = os.getenv("APPLE_AUDIENCE", "").strip()  # Services ID (web) or Bundle ID (iOS)

# ---- Google env ----
GOOGLE_ISS: str = os.getenv("GOOGLE_ISS", "https://accounts.google.com")
GOOGLE_JWKS_URI: str = os.getenv("GOOGLE_JWKS_URI", "https://www.googleapis.com/oauth2/v3/certs")
GOOGLE_AUD: str = os.getenv("GOOGLE_AUDIENCE", "").strip()  # OAuth client id: <project-id>.apps.googleusercontent.com

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
        )
        return claims

class MultiIssuerVerifier:
    """
    Chooses the right verifier based on the token's 'iss' claim, then verifies.
    """
    def __init__(self, verifiers: List[OIDCVerifier]):
        # If multiple verifiers share the same issuer, last one wins (unlikely)
        self._by_iss: Dict[str, OIDCVerifier] = {v.iss: v for v in verifiers}

    def verify(self, token: str) -> Dict:
        # Peek at the unverified payload to route by 'iss'
        # NOTE: verify_signature=False is safe here because we immediately re-verify with JWKS.
        hdrless = jwt.decode(token, options={"verify_signature": False})
        iss = hdrless.get("iss")
        v = self._by_iss.get(iss)
        if not v:
            raise ValueError(f"untrusted issuer: {iss}")
        return v.verify(token)

def build_multi_from_env() -> MultiIssuerVerifier:
    """
    Build a multi-issuer verifier from environment configuration.

    Enable a provider by setting its AUDIENCE:
      - APPLE_AUDIENCE = com.yourco.marketgemini.web  (Services ID)  OR an iOS Bundle ID
      - GOOGLE_AUDIENCE = 1234567890-abc.apps.googleusercontent.com  (OAuth client id)
    """
    verifiers: List[OIDCVerifier] = []

    # Apple (enabled only if audience is set)
    if APPLE_AUD:
        verifiers.append(
            OIDCVerifier(
                iss=APPLE_ISS,
                jwks_uri=APPLE_JWKS_URI,
                audiences=[APPLE_AUD],
                algs=("RS256",),
            )
        )

    # Google (enabled only if audience is set)
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
        # Be explicit to help during config
        raise RuntimeError(
            "No OIDC providers configured. "
            "Set APPLE_AUDIENCE and/or GOOGLE_AUDIENCE in your environment."
        )

    return MultiIssuerVerifier(verifiers)
