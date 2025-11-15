from fastapi import FastAPI, Request
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
# ... CORS etc ...

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
