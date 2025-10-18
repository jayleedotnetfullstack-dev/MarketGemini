from typing import Optional
from fastapi import Header, HTTPException, status
from .auth import verify_bearer  # HS256 verifier you already have

def hs256_required(required_scope: Optional[str] = None):
    async def dep(authorization: str = Header(None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
        token = authorization.split(" ", 1)[1]
        return verify_bearer(token, required_scope)
    return dep
