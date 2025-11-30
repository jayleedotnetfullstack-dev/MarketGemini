# app/schemas/core.py
from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel


# ============================================================
# Provider Enumeration
# ============================================================

class Provider(str, Enum):
    gemini = "gemini"
    openai = "openai"
    deepseek = "deepseek"
    # extend later: anthropic, llama, perplexity, etc.


# User-selected profile category (not model)
ProfileId = Literal["factual", "summary", "creative", "code", "ensemble"]


# ============================================================
# DeepSeek Mode Enumeration
# ============================================================

class DeepseekMode(str, Enum):
    auto = "auto"     # router auto-classifies into chat/v3/r1
    chat = "chat"
    v3 = "v3"
    r1 = "r1"


# ============================================================
# Basic message model
# ============================================================

class Message(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


# ============================================================
# Consolidation (ensemble) configuration
# ============================================================

class ConsolidateConfig(BaseModel):
    enabled: bool = True
    provider: Provider
    model: str


# ============================================================
# DeepSeek routing info (returned for transparency)
# ============================================================

class DeepseekRoutingInfo(BaseModel):
    requested_mode: DeepseekMode                   # user selected ("auto"/"chat"/"v3"/"r1")
    resolved_model: str                            # actual model used ("deepseek-chat"/"deepseek-v3"/"deepseek-r1")
    auto_recommended_model: Optional[str] = None   # classifier suggestion
    confidence_score: float                        # 0–1
    confidence_label: Literal["HIGH", "MEDIUM", "LOW"]
    confidence_message: Optional[str] = None       # free text explanation


# ============================================================
# RouterChatRequest
# ============================================================

class RouterChatRequest(BaseModel):
    session_id: str
    profile: ProfileId
    providers: List[Provider]
    messages: List[Message]
    consolidate: ConsolidateConfig

    # dict mapping provider → model hint
    #   e.g. { "deepseek": "v3", "gemini": "gemini-pro" }
    model_hint_map: Dict[Provider, Optional[str]] = {}

    # DeepSeek manual/auto selection
    deepseek_mode: DeepseekMode = DeepseekMode.auto

    # NEW (Phase 4): optional dev-only identity override.
    # Example JSON:
    #   "debug_identity": {
    #       "provider": "google",
    #       "provider_sub": "1234567890",
    #       "email": "user@example.com",
    #       "display_name": "Example User"
    #   }
    debug_identity: Optional[Dict[str, str]] = None


# ============================================================
# RouterResultItem  (per-provider response)
# ============================================================

class RouterResultItem(BaseModel):
    provider: Provider
    model: str                    # actual model ID used
    profile: ProfileId            # user-selected (single call) or "ensemble"
    content: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float
    confidence: Optional[float] = None


# ============================================================
# FinalResult (combined / final answer)
# ============================================================

class FinalResult(BaseModel):
    content: str
    strategy: Literal["single_model", "ensemble"]

    # DeepSeek routing transparency (if DeepSeek was called)
    deepseek_routing: Optional[DeepseekRoutingInfo] = None

    # explicit final model (for UI display)
    provider: Optional[Provider] = None
    model: Optional[str] = None

    # estimated total cost across providers
    estimated_cost_usd: Optional[float] = None


# ============================================================
# RouterChatResponse
# ============================================================

class RouterChatResponse(BaseModel):
    final: FinalResult
    results: List[RouterResultItem]


# ============================================================
# Digest request / response (used by /v1/digest)
# ============================================================

Role = Literal["user", "assistant", "system"]


class DigestMessage(BaseModel):
    role: Role
    content: str


class DigestRequest(BaseModel):
    user_id: str
    session_id: str
    messages: List[DigestMessage]


class DigestResponse(BaseModel):
    intent: str
    # add more fields later if needed
