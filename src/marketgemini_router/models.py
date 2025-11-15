# src/marketgemini_router/models.py
from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel

Role = Literal["system", "user", "assistant"]

class ChatMessage(BaseModel):
    role: Role
    content: str

class ChatRequest(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    messages: List[ChatMessage]
    profile: Optional[str] = None  # for routing / temperature profile
