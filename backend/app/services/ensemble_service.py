import time
import os
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import (
    RouterChatRequest,
    RouterResultItem,
    FinalResult,
    Provider,
)
from app.routing.prompt_helpers import extract_prompt
from app.services.logging_service import log_invocation
from app.providers.gemini_provider import call_gemini_api
from app.providers.deepseek_provider import DeepseekProvider
from app.routing.deepseek_pricing import estimate_deepseek_cost


def _build_consolidation_prompt(
    req: RouterChatRequest,
    base_results: List[RouterResultItem],
) -> str:
    user_prompt = extract_prompt(req.messages)

    lines: list[str] = [
        "You are an ensemble model that consolidates multiple model outputs.",
        "",
        "Original user prompt:",
        user_prompt,
        "",
        "Below are answers from different models/providers.",
        "Your job is to:",
        "- Identify and correct factual errors.",
        "- Resolve contradictions.",
        "- Produce a single, clear, structured answer.",
        "",
        "Model answers:",
    ]

    for r in base_results:
        lines.append(
            f"--- Provider={r.provider.value}, model={r.model}, profile={r.profile}, "
            f"cost={r.cost_usd}, latency={r.latency_ms}ms ---"
        )
        lines.append(r.content)
        lines.append("")

    lines.append(
        "Now produce a single consolidated answer for the user. "
        "Prefer correctness, clarity, and explicit caveats if uncertain."
    )
    return "\n".join(lines)


async def _call_ensemble_provider(
    db: AsyncSession,
    *,
    user,
    session,
    provider: Provider,
    model_hint: str | None,
    profile: str,
    consolidation_text: str,
    router_request_id,
) -> RouterResultItem:
    """
    A lightweight, provider-aware call used ONLY for ensemble consolidation.
    Keeps logic isolated from normal per-provider calls to avoid circular imports.
    """
    start = time.perf_counter()
    tokens_in = 0
    tokens_out = 0
    cost_usd = 0.0
    model_used = model_hint or "unknown"
    confidence = 0.9
    success = True
    error_code = None
    content = ""

    messages = [{"role": "user", "content": consolidation_text}]

    try:
        if provider == Provider.gemini:
            content, tokens_in, tokens_out, model_used = await call_gemini_api(
                messages, model_hint
            )
            # TODO: add actual Gemini pricing if desired
            cost_usd = 0.0
            confidence = 0.92

        elif provider == Provider.deepseek:
            # Ensemble via DeepSeek is supported but less common.
            # We use v3 as a good general-purpose model.
            ds_model = model_hint or "deepseek-v3"
            client = DeepseekProvider(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                model=ds_model,
            )
            content, tokens_in, tokens_out = await client.invoke(messages)
            cost_usd = estimate_deepseek_cost(ds_model, tokens_in, tokens_out)
            model_used = ds_model
            confidence = 0.9

        else:
            content = (
                f"[ENSEMBLE] Provider {provider.value} not implemented; "
                "please configure consolidate.provider accordingly."
            )
            model_used = f"{provider.value}-ensemble"
            confidence = 0.5

    except Exception as ex:
        success = False
        error_code = type(ex).__name__
        content = f"[ENSEMBLE ERROR] {ex}"
        confidence = 0.0

    latency_ms = int((time.perf_counter() - start) * 1000)

    await log_invocation(
        db,
        user_id=user.id,
        session_id=session.id,
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
        cost_usd=cost_usd,
        confidence=confidence,
    )


async def build_and_call_ensemble(
    req: RouterChatRequest,
    db: AsyncSession,
    user,
    session,
    router_request,
    base_results: List[RouterResultItem],
) -> FinalResult:
    """
    Build consolidation prompt from base_results and call the selected ensemble provider.
    """
    consolidation_text = _build_consolidation_prompt(req, base_results)

    ensemble_item = await _call_ensemble_provider(
        db=db,
        user=user,
        session=session,
        provider=req.consolidate.provider,
        model_hint=req.consolidate.model,
        profile="ensemble",
        consolidation_text=consolidation_text,
        router_request_id=router_request.id,
    )

    return FinalResult(
        content=ensemble_item.content,
        strategy="ensemble",
        provider=ensemble_item.provider,
        model=ensemble_item.model,
        estimated_cost_usd=ensemble_item.cost_usd,
        deepseek_routing=None,  # call_providers will attach if DeepSeek involved
    )
