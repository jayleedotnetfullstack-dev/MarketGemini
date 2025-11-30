# backend/app/schemas/identity.py

from typing import Optional

from pydantic import BaseModel


class UserIdentityInfo(BaseModel):
    """
    Lightweight Pydantic model representing an external login identity.

    This is used purely at the API / service layer to describe
    "who the user is" as reported by Google / Apple / MSFT / Deepseek / etc.

    Fields:
      - provider: which auth provider issued this identity
      - provider_sub: stable unique subject / id from that provider
      - email: optional email (if provider gives it)
      - display_name: optional human-readable name
    """

    # e.g. "google", "apple", "msft", "deepseek", "local"
    provider: str

    # stable unique ID from that provider (e.g. Google 'sub', MSFT oid)
    provider_sub: str

    # optional convenience fields
    email: Optional[str] = None
    display_name: Optional[str] = None
