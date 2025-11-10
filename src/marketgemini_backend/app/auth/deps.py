# src/marketgemini_backend/app/auth/deps.py
from __future__ import annotations
from typing import Optional
from fastapi import Header, HTTPException, status

# Import your internal HS256 verifier (you already have this in auth/internal.py)
from marketgemini_backend.app.auth.internal import verify_bearer

def require_scope(required: Optional[str] = None):
    """
    Factory that returns an async FastAPI dependency.
    IMPORTANT: This outer function is SYNC and returns an ASYNC inner function.
    Do NOT make this outer function async.
    """
    async def _dep(authorization: Optional[str] = Header(None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
        token = authorization.split(" ", 1)[1].strip()
        # This verifies HS256 token (issuer/audience/exp/scope)
        claims = verify_bearer(token, required_scope=required)
        return claims  # available to handlers if you need the claims
    return _dep
