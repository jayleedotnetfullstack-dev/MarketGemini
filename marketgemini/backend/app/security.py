# backend/app/security.py
import os
from typing import Optional
from .security_hs256 import hs256_required
from .security_oidc import oidc_required

AUTH_MODE = os.getenv("AUTH_MODE", "HS256").upper()  # HS256 or OIDC

def auth_required(required_scope: Optional[str] = None):
    mode = (os.getenv("AUTH_MODE", "HS256") or "").strip().upper()
    return oidc_required(required_scope) if mode == "OIDC" else hs256_required(required_scope)

