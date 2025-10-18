import os, time, jwt
from dotenv import load_dotenv
from fastapi import HTTPException, status
load_dotenv()
JWT_SECRET = os.getenv("JWT_SECRET", "dev_secret_do_not_use_in_prod")
JWT_ISS    = os.getenv("JWT_ISS", "marketgemini")
JWT_AUD    = os.getenv("JWT_AUD", "marketgemini-api")
ALGO       = "HS256"
def make_dev_token(sub: str = "dev-user", ttl_sec: int = 900, scope: str = "series:read analyze:run") -> str:
    now = int(time.time())
    payload = {"sub": sub, "iss": JWT_ISS, "aud": JWT_AUD, "iat": now, "nbf": now, "exp": now+ttl_sec, "scope": scope}
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGO)
def verify_bearer(token: str, required_scope: str | None = None) -> dict:
    try:
        claims = jwt.decode(
            token, JWT_SECRET, algorithms=[ALGO],
            audience=JWT_AUD, issuer=JWT_ISS,
            options={"require": ["exp","iss","aud"]}
        )
    except jwt.PyJWTError as ex:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid token: {ex}")
    if required_scope:
        scopes = set((claims.get("scope") or "").split())
        if required_scope not in scopes:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient_scope")
    return claims
