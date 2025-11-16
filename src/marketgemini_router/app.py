from typing import Any, Dict, List  # 👈 add this

from fastapi import FastAPI, Request, Body   # 👈 add Body
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from dotenv import load_dotenv
import traceback

from marketgemini_router.core.config import CFG, get_provider_cfg
from marketgemini_router.core.clean import clean_prompt
from marketgemini_router.core.detect import auto_profile_for_messages
from marketgemini_router.core.reward import calc_cost
from marketgemini_router.adapters import gemini, openai, deepseek, ollama_dev

from marketgemini_router.models import ChatRequest
from marketgemini_router.memory.service import (
    MemoryService,
    assert_single_user_context,
    build_memory_context,
)

# Load .env from project root: C:\jay\ProjectAI\.env
ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

app = FastAPI(title="MarketGemini Router", version="0.1")

# CORS so router can be called from Vite dev server (5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

memory_service = MemoryService()


def call_adapter(provider: str, pcfg: dict, msgs: list[dict], profile: str):
    if provider == "gemini":
        return gemini.chat(pcfg, msgs, profile)
    elif provider == "openai":
        return openai.chat(pcfg, msgs, profile)
    elif provider == "deepseek":
        return deepseek.chat(pcfg, msgs, profile)
    else:
        return ollama_dev.chat(pcfg, msgs, profile)


# 🔹 NEW: light-weight prompt analysis endpoint for the React UI
@app.post("/v1/digest")
async def digest_prompt(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """
    Analyze the last user message:
    - guess intent / router profile
    - compute a confidence score
    - optionally clean the prompt
    - return rewrite suggestions if confidence is low
    """
    # 1) Extract messages (OpenAI-style)
    messages: List[Dict[str, str]] = payload.get("messages") or []
    text = ""
    if messages:
        last = messages[-1]
        text = last.get("content", "") or ""

    # 2) Empty text → low confidence, suggest user to write something clearer
    if not text.strip():
        return {
            "intent": "unknown",
            "profile": "summary",
            "confidence": 0.0,
            "cleaned_prompt": "",
            "suggestions": [
                "Please type a clear question or instruction, e.g. 'Summarize today’s gold price drivers in 3 bullets.'"
            ],
        }

    # 3) Decide profile using your existing auto_profile_for_messages
    try:
        profile = auto_profile_for_messages(
            messages,
            explicit=payload.get("profile"),
        )
    except Exception:
        profile = payload.get("profile") or "summary"

    # 4) Clean the prompt using your existing cleaner
    try:
        cleaned_messages = clean_prompt(messages)
        cleaned_text = cleaned_messages[-1].get("content", text) if cleaned_messages else text
    except Exception:
        cleaned_text = text

    # 5) Simple heuristic intent + confidence
    lc = text.lower()
    if any(k in lc for k in ["summarize", "summary", "explain", "analyze", "overview"]):
        intent = "summary"
        confidence = 0.85
    elif any(k in lc for k in ["code", "bug", "exception", "stack trace", "c#", "python", "java"]):
        intent = "code"
        confidence = 0.8
    elif any(k in lc for k in ["rewrite", "rephrase", "improve wording", "polish"]):
        intent = "rewrite"
        confidence = 0.8
    else:
        intent = "general"
        confidence = 0.6

    # Adjust confidence by length
    if len(text) < 16:
        confidence = min(confidence, 0.5)
    if len(text) > 300:
        confidence = max(confidence, 0.75)

    # 6) Suggestions if confidence is low
    suggestions: List[str] = []
    if confidence < 0.7:
        suggestions.append(
            "Rewrite with more context, e.g. 'Summarize the main drivers of gold prices in 3 bullets, focusing on macro factors and market sentiment.'"
        )
        suggestions.append(
            "Add constraints like 'in 5 bullets', 'explain step-by-step', or 'focus on beginners'."
        )

    return {
        "intent": intent,
        "profile": profile,
        "confidence": confidence,
        "cleaned_prompt": cleaned_text,
        "suggestions": suggestions,
    }


@app.post("/v1/chat")
async def chat(request: Request):
    raw = await request.json()
    req = ChatRequest(**raw)

    if not req.messages:
        return {
            "provider": "router",
            "model": "n/a",
            "mode": "ERROR",
            "content": "[input] 'messages' must be non-empty",
        }

    user_id = req.user_id
    session_id = req.session_id

    # 1) Decide profile (task=auto supported)
    profile = auto_profile_for_messages(
        [m.model_dump() for m in req.messages],
        explicit=req.profile,
    )

    # 2) Load memory
    try:
        mem_items = memory_service.get_recent_memory(user_id=user_id, limit=8)
    except NotImplementedError:
        mem_items = []
    assert_single_user_context(mem_items, expected_user_id=user_id)
    mem_context = build_memory_context(mem_items)

    llm_messages = [m.model_dump() for m in req.messages]
    if mem_context:
        llm_messages.insert(0, {"role": "system", "content": mem_context})

    # 3) Clean prompt
    clean_msgs = clean_prompt(llm_messages)

    # 4) Cost-aware provider selection
    provider, pcfg = get_provider_cfg(profile, CFG, clean_msgs)

    # 5) Call adapter
    content, ti, to, dur = call_adapter(provider, pcfg, clean_msgs, profile)

    # 6) Cost calc
    cost_usd = calc_cost(provider, ti, to)

    # 7) Store memory event (best-effort)
    try:
        memory_service.add_event(
            user_id=user_id,
            session_id=session_id,
            kind="query",
            text=req.messages[-1].content[:512],
        )
    except NotImplementedError:
        pass

    return {
        "provider": provider,
            "model": pcfg["model"],
            "mode": "EXECUTE",
            "content": content,
            "tokens_in": ti,
            "tokens_out": to,
            "latency_ms": dur,
            "cost_usd": cost_usd,
            "profile": profile,
    }
