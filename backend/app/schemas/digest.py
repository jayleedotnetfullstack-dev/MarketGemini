# backend/app/schemas/digest.py

from typing import List, Literal, Optional

from pydantic import BaseModel


class DigestMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class DigestRequest(BaseModel):
    user_id: str
    session_id: str
    messages: List[DigestMessage]

class DigestResponse(BaseModel):
    intent: str
    profile: str                          # 👈 exposed to UI
    confidence: float
    type: Literal["optimized", "user_guidance", "neutral"]
    cleaned_prompt: Optional[str] = None
    suggested_prompt: Optional[str] = None
    suggestions: Optional[List[str]] = None   # 👈 exposed to UI