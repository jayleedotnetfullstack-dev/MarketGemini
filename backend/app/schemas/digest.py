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
    cleaned_prompt: Optional[str] = None
