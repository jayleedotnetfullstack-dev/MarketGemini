# backend/app/schemas/auth.py

from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr


class UserIdentityInfo(BaseModel):
    """
    Generic “who is this external user?” DTO.

    This is what your auth layer (Google, Apple, MSFT, DeepSeek, or
    your own username/password) will populate and pass into the
    backend core.

    It is intentionally provider-agnostic.
    """

    # e.g. "google", "apple", "microsoft", "deepseek", "local"
    provider: str

    # The stable subject / user id from that provider
    # e.g. Google "sub" claim, MSFT "oid", Apple "sub", etc.
    provider_sub: str

    # Optional but very useful for linking users
    email: Optional[EmailStr] = None

    # Human-friendly name (from Google profile, MSFT displayName, etc.)
    display_name: Optional[str] = None

    # Optional raw claims or extra data (for debugging / analytics)
    raw_claims: Optional[Dict[str, Any]] = None
