# src/marketgemini_backend/app/security/hs256.py
from __future__ import annotations
from typing import Optional

from marketgemini_backend.app.auth.internal import require_scope as _require_scope_internal

def hs256_required(required_scope: Optional[str] = None):
    """
    HS256-only route dependency.
    Equivalent to internal.require_scope(required_scope).
    """
    return _require_scope_internal(required_scope)
