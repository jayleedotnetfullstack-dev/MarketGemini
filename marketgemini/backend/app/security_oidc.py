from typing import Optional
from fastapi import Header, HTTPException, status
from .oidc import build_multi_from_env  # builds MultiIssuerVerifier(Apple[, Google...])

_oidc_multi = build_multi_from_env()

def oidc_required(required_scope: Optional[str] = None):
    async def dep(authorization: str = Header(None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
        token = authorization.split(" ", 1)[1]

        try:
            claims = _oidc_multi.verify(token)  # verifies iss/aud/exp/signature
        except Exception as ex:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid or expired token: {ex}")

        # Optional scope enforcement if you add scopes to IdP tokens
        if required_scope:
            scopes = (claims.get("scope") or claims.get("scp") or "")
            if required_scope not in scopes.split():
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_scope")

        return claims
    return dep
