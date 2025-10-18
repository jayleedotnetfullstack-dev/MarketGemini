import os, jwt
from fastapi import Header, HTTPException
from .auth_internal import verify_access

def internal_required(required_scope: str | None = None):
    async def dep(authorization: str = Header(None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "missing bearer token")
        token = authorization.split(" ", 1)[1]
        try:
            claims = verify_access(token)
        except jwt.ExpiredSignatureError:
            raise HTTPException(401, "access token expired",
                                headers={"WWW-Authenticate": 'Bearer error="invalid_token", error_description="expired"'})
        except jwt.PyJWTError as ex:
            raise HTTPException(401, f"invalid access token: {ex}")
        if required_scope:
            scopes = set((claims.get("scope") or "").split())
            if required_scope not in scopes:
                raise HTTPException(403, "insufficient permissions")
        return {"claims": claims}
    return dep
