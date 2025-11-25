from pydantic import BaseModel
from typing import List, Literal, Optional

Provider = Literal["gemini", "openai", "deepseek"]
ProfileId = Literal["factual", "summary", "creative", "code"]

class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ConsolidateConfig(BaseModel):
    enabled: bool = True
    provider: Provider
    model: str

class RouterChatRequest(BaseModel):
    session_id: str
    profile: ProfileId
    providers: List[Provider]
    messages: List[Message]
    consolidate: ConsolidateConfig

class RouterResultItem(BaseModel):
    provider: Provider
    model: str
    profile: ProfileId   # base calls: user-selected profile; ensemble = "ensemble"
    content: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float
    confidence: Optional[float] = None

class FinalResult(BaseModel):
    content: str
    strategy: Literal["single_model", "highest_confidence", "ensemble"]

class RouterChatResponse(BaseModel):
    final: FinalResult
    results: List[RouterResultItem]
