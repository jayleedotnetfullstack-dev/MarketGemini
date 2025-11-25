import uuid
import time
import asyncio
import os
import random
from typing import List, Optional, Literal, Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .schemas import (
    RouterChatRequest,
    RouterChatResponse,
    RouterResultItem,
    FinalResult,
    Provider,
)

from .db import get_db
from .models import User, Session, AiRouterRequest, AiInvocation


router = APIRouter()

# ============================================================
#  /v1/digest  (used by Analyze / Digest button in the UI)
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
    profile: str
    confidence: float
    cleaned_prompt: str
    suggestions: List[str]


@router.post("/v1/digest", response_model=DigestResponse)
async def digest(req: DigestRequest) -> DigestResponse:
    """
    Heuristic digest:
    - Computes confidence based on prompt length / richness
    - Returns suggestions when the prompt is too short or too long
    """
    raw = _extract_prompt_from_messages(req.messages)
    text = (raw or "").strip()
    words = text.split()
    word_count = len(words)
    char_len = len(text)

    intent = "general_question"
    profile = "summary"
    confidence = 0.85
    suggestions: List[str] = []

    # Very vague: "why?", "help", "?", etc.
    if char_len < 5 or word_count <= 1:
        intent = "too_vague"
        confidence = 0.20
        suggestions.append(
            "Your prompt is too short. Please add what topic or situation you're asking about."
        )
        suggestions.append(
            "Example: instead of 'why?', try 'Why did gold prices rise in 2024?'"
        )

    # Short / low-context: "why gold?", "explain inflation"
    elif word_count < 5:
        intent = "vague"
        confidence = 0.45
        suggestions.append(
            "Try adding a bit more context (who/what/when) so the answer can be more precise."
        )
        suggestions.append(
            "Example: 'Explain how inflation affects long-term mortgage rates in the US.'"
        )

    # Very long / rambling
    elif word_count > 40:
        intent = "long_question"
        confidence = 0.70
        suggestions.append(
            "Your question is quite long. Consider summarizing the key points to get a sharper answer."
        )

    # Normal, well-sized question
    else:
        intent = "well_formed"
        confidence = 0.90

    return DigestResponse(
        intent=intent,
        profile=profile,
        confidence=confidence,
        cleaned_prompt=text or raw,
        suggestions=suggestions,
    )


# ============================================================
#  Helpers for router_chat
# ============================================================

async def get_current_user(db: AsyncSession = Depends(get_db)) -> User:
    stmt = select(User).where(User.external_id == "router-lab")
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            external_id="router-lab",
            display_name="Router Lab",
            email=None,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


async def get_or_create_session(
    db: AsyncSession,
    user_id,
    session_id_str: str,
) -> Session:
    try:
        session_uuid = uuid.UUID(session_id_str)
    except ValueError:
        session_uuid = uuid.uuid4()

    stmt = select(Session).where(Session.id == session_uuid)
    result = await db.execute(stmt)
    sess = result.scalar_one_or_none()
    if sess:
        return sess

    sess = Session(
        id=session_uuid,
        user_id=user_id,
        title="Router Lab Session",
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)
    return sess


async def log_invocation(
    db: AsyncSession,
    *,
    user_id,
    session_id,
    router_request_id,
    provider: Provider,
    model: str,
    profile: str,
    confidence: Optional[float],
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    latency_ms: int,
    success: bool,
    error_code: Optional[str],
) -> None:
    inv = AiInvocation(
        user_id=user_id,
        session_id=session_id,
        router_request_id=router_request_id,
        provider=provider,
        model=model,
        profile=profile,
        confidence=confidence,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        tokens_total=(tokens_in or 0) + (tokens_out or 0),
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        success=success,
        error_code=error_code,
    )
    db.add(inv)
    await db.commit()


# ============================================================
#  Gemini provider helper
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_DEFAULT = os.getenv("GEMINI_MODEL_DEFAULT", "gemini-2.0-flash")


def _extract_prompt_from_messages(messages: List[Any]) -> str:
    """Support both Pydantic objects and plain dicts for messages."""
    if not messages:
        return ""
    last = messages[-1]
    if hasattr(last, "content"):
        return last.content
    if isinstance(last, dict) and "content" in last:
        return str(last["content"])
    return str(last)


async def call_gemini_api(
    messages: List[Any],
    model_hint: Optional[str],
) -> tuple[str, int, int, str]:
    """
    Gemini API call with exponential backoff retry handling.
    Returns: (content, tokens_in, tokens_out, model_used)
    """
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set in environment")

    prompt = _extract_prompt_from_messages(messages)
    model = model_hint or GEMINI_MODEL_DEFAULT

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": prompt}]}
        ]
    }

    max_attempts = 5
    backoff = 1.0  # seconds

    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)

            # Handle rate limiting or transient errors with retry
            if resp.status_code in (429, 503) and attempt < max_attempts - 1:
                await asyncio.sleep(backoff + random.random())
                backoff *= 2
                continue

            resp.raise_for_status()
            data = resp.json()

            candidates = data.get("candidates") or []
            if not candidates:
                raise RuntimeError("Gemini returned no candidates")

            parts = candidates[0].get("content", {}).get("parts") or []
            if not parts:
                raise RuntimeError("Gemini returned empty content parts")

            content = parts[0].get("text", "")

            usage = data.get("usageMetadata") or {}
            tokens_in = usage.get("promptTokenCount", 0)
            tokens_out = usage.get("candidatesTokenCount", 0)

            return content, tokens_in, tokens_out, model

        except httpx.HTTPStatusError as e:
            # Retry only for 429 / 503 when attempts remain
            if (
                e.response is not None
                and e.response.status_code in (429, 503)
                and attempt < max_attempts - 1
            ):
                await asyncio.sleep(backoff + random.random())
                backoff *= 2
                continue
            raise
        except httpx.RequestError:
            # Network-level error; optionally retry as well
            if attempt < max_attempts - 1:
                await asyncio.sleep(backoff + random.random())
                backoff *= 2
                continue
            raise

    raise RuntimeError("Gemini failed after retries")


# ============================================================
#  Single-provider call (Gemini + future others)
# ============================================================

async def call_single_provider(
    db: AsyncSession,
    *,
    user_id,
    session_id,
    router_request_id,
    provider: Provider,
    model_hint: Optional[str],
    profile: str,
    messages,
) -> RouterResultItem:

    start = time.perf_counter()
    success = True
    error_code = None

    # Defaults for unimplemented providers or failure
    tokens_in = 0
    tokens_out = 0
    cost_usd = 0.0
    confidence = 0.80
    content = f"[DEMO] {provider} ({profile}) would answer here."
    model_used = model_hint or f"{provider}-demo-model"

    try:
        if provider == "gemini":
            # Real Gemini call
            content, tokens_in, tokens_out, model_used = await call_gemini_api(
                messages=messages,
                model_hint=model_hint,
            )
            # You can refine these based on actual pricing
            cost_usd = 0.0
            confidence = 0.88

        else:
            # TODO: implement real calls for chatgpt / deepseek
            pass

    except Exception as ex:
        success = False
        error_code = type(ex).__name__
        content = f"Error from {provider}: {ex}"

    latency_ms = int((time.perf_counter() - start) * 1000)

    await log_invocation(
        db,
        user_id=user_id,
        session_id=session_id,
        router_request_id=router_request_id,
        provider=provider,
        model=model_used,
        profile=profile,
        confidence=confidence,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        success=success,
        error_code=error_code,
    )

    return RouterResultItem(
        provider=provider,
        model=model_used,
        profile=profile,
        content=content,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        latency_ms=latency_ms,
        cost_usd=float(cost_usd or 0.0),
        confidence=confidence,
    )


def build_consolidation_prompt(messages, base_results: List[RouterResultItem]) -> str:
    user_prompt = _extract_prompt_from_messages(messages)
    lines = [
        "You are an ensemble model that consolidates multiple model outputs.",
        "",
        "Original user prompt:",
        user_prompt,
        "",
        "Model answers:",
    ]
    for r in base_results:
        lines.append(
            f"- Provider={r.provider}, model={r.model}, profile={r.profile}, "
            f"cost={r.cost_usd}, latency={r.latency_ms}ms"
        )
        lines.append(r.content)
        lines.append("")
    lines.append("Please produce a single consolidated answer.")
    return "\n".join(lines)


# ============================================================
#  /v1/router/chat
# ============================================================

@router.post("/v1/router/chat", response_model=RouterChatResponse)
async def router_chat(
    req: RouterChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not req.providers:
        raise HTTPException(status_code=400, detail="At least one provider required")

    session = await get_or_create_session(db, user.id, req.session_id)

    rr = AiRouterRequest(
        user_id=user.id,
        session_id=session.id,
        profile=req.profile,
    )
    db.add(rr)
    await db.commit()
    await db.refresh(rr)

    # --- Base model calls ---
    base_tasks = [
        call_single_provider(
            db,
            user_id=user.id,
            session_id=session.id,
            router_request_id=rr.id,
            provider=p,
            model_hint=None,
            profile=req.profile,
            messages=req.messages,
        )
        for p in req.providers
    ]
    base_results = await asyncio.gather(*base_tasks)

    # --- No ensemble needed ---
    if len(base_results) == 1 or not req.consolidate.enabled:
        final_item = base_results[0]
        return RouterChatResponse(
            final=FinalResult(
                content=final_item.content,
                strategy="single_model",
            ),
            results=base_results,
        )

    # --- Ensemble ---
    consolidation_text = build_consolidation_prompt(req.messages, base_results)

    ensemble_result = await call_single_provider(
        db,
        user_id=user.id,
        session_id=session.id,
        router_request_id=rr.id,
        provider=req.consolidate.provider,
        model_hint=req.consolidate.model,
        profile="ensemble",
        messages=[{"role": "user", "content": consolidation_text}],
    )

    return RouterChatResponse(
        final=FinalResult(
            content=ensemble_result.content,
            strategy="ensemble",
        ),
        results=base_results,
    )
