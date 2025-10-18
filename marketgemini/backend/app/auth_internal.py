import os, time, jwt
from typing import Optional, Dict, Any

JWT_SECRET = os.getenv("JWT_SECRET", "dev_change_me")
JWT_ISS    = os.getenv("JWT_ISS", "marketgemini")
JWT_AUD    = os.getenv("JWT_AUD", "marketgemini-api")

ACCESS_TTL = int(os.getenv("JWT_ACCESS_TTL_SEC", "900"))        # 15m
REFRESH_TTL = int(os.getenv("JWT_REFRESH_TTL_SEC", "2592000"))  # 30d

def _now() -> int: return int(time.time())

def issue_access_token(sub: str, scope: str = "series:read analyze:run",
                       extra: Optional[Dict[str, Any]] = None,
                       ttl: Optional[int] = None) -> str:
    now = _now()
    payload = {
        "iss": JWT_ISS, "aud": JWT_AUD, "sub": sub, "scope": scope,
        "iat": now, "nbf": now, "exp": now + (ttl or ACCESS_TTL)
    }
    if extra: payload.update(extra)
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def issue_refresh_token(sub: str, ttl: Optional[int] = None) -> str:
    now = _now()
    payload = {
        "iss": JWT_ISS, "aud": JWT_AUD, "sub": sub,
        "iat": now, "nbf": now, "exp": now + (ttl or REFRESH_TTL),
        "typ": "refresh"
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def verify_access(token: str) -> Dict[str, Any]:
    return jwt.decode(
        token, JWT_SECRET, algorithms=["HS256"],
        audience=JWT_AUD, issuer=JWT_ISS,
        options={"require": ["exp", "iss", "aud"]}
    )

def verify_refresh(token: str) -> Dict[str, Any]:
    claims = jwt.decode(
        token, JWT_SECRET, algorithms=["HS256"],
        audience=JWT_AUD, issuer=JWT_ISS,
        options={"require": ["exp", "iss", "aud"]}
    )
    if claims.get("typ") != "refresh":
        raise jwt.InvalidTokenError("not a refresh token")
    return claims
