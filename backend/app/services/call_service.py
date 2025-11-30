import time
import asyncio
import os
from typing import Tuple, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import (
    Provider,
    RouterChatRequest,
    RouterResultItem,
    FinalResult,
    DeepseekMode,
    DeepseekRoutingInfo,
)

from app.services.logging_service import log_invocation
from app.providers.gemini_provider import call_gemini_api
from app.providers.deepseek_provider import DeepseekProvider

from app.routing.prompt_helpers import extract_prompt
from app.routing.deepseek_classifier import (
    classify_deepseek_model,
    confidence_label,
    DeepseekResolvedModel,
)

from app.routing.deepseek_pricing import estimate_deepseek_cost
from app.db.models import AiRouterRequest

from typing import Any, List, Dict

def _normalize_messages_for_llm(messages: List[Any]) -> List[Dict[str, str]]:
    """
    Convert RouterChatRequest.messages (which may be Pydantic Message objects)
    into a list of plain dicts: {"role": ..., "content": ...} that
    the DeepSeek/OpenAI-style client can JSON-serialize.
    """
    normalized: List[Dict[str, str]] = []
    for m in messages:
        # Pydantic v2 model
        if hasattr(m, "model_dump"):
            data = m.model_dump()
            role = data.get("role")
            content = data.get("content")
        # Pydantic v1 model
        elif hasattr(m, "dict"):
            data = m.dict()
            role = data.get("role")
            content = data.get("content")
        # Already a dict
        elif isinstance(m, dict):
            role = m.get("role")
            content = m.get("content")
        else:
            # Fallback: best-effort attribute access
            role = getattr(m, "role", None)
            content = getattr(m, "content", None)

        if role is None or content is None:
            # optional: you can log or raise here
            continue

        normalized.append(
            {
                "role": str(role),
                "content": str(content),
            }
        )
    return normalized

# ============================================================
#  Single provider call
# ============================================================

async def call_single(
    db: AsyncSession,
    *,
    user,
    session,
    rr: AiRouterRequest,
    provider: Provider,
    model_hint: str | None,
    profile: str,
    messages,
) -> Tuple[RouterResultItem, DeepseekRoutingInfo | None]:
    start = time.perf_counter()

    # Defaults
    tokens_in = 0
    tokens_out = 0
    cost_usd = 0.0
    model_used = model_hint or "unknown"
    confidence = 0.5
    content = ""
    success = True
    error_code = None
    deepseek_routing_info: DeepseekRoutingInfo | None = None

    try:
        # ---------------------------------------------------------
        # GEMINI
        # ---------------------------------------------------------
        if provider == Provider.gemini:
            content, tokens_in, tokens_out, model_used = await call_gemini_api(
                messages, model_hint
            )
            # TODO: plug in real Gemini pricing if/when you want
            cost_usd = 0.0
            confidence = 0.88

        # ---------------------------------------------------------
        # DEEPSEEK (AUTO + MANUAL)
        # ---------------------------------------------------------
        elif provider == Provider.deepseek:
            last_prompt = extract_prompt(messages)

            # Classifier recommendation
            auto_model_enum, conf_score, reason = classify_deepseek_model(last_prompt)
            auto_model_id = auto_model_enum.value  # e.g. "deepseek-chat"

            # model_hint carries "auto" | "chat" | "v3" | "r1" from the UI
            # If it's missing/invalid, default to DeepseekMode.auto.
            selected_mode_str = model_hint or DeepseekMode.auto.value
            try:
                requested_mode = DeepseekMode(selected_mode_str)
            except ValueError:
                requested_mode = DeepseekMode.auto

            # Resolve actual DeepSeek model ID to call
            if requested_mode == DeepseekMode.auto:
                resolved_id = auto_model_id
            elif requested_mode == DeepseekMode.chat:
                resolved_id = DeepseekResolvedModel.chat.value
            elif requested_mode == DeepseekMode.v3:
                resolved_id = DeepseekResolvedModel.v3.value
            elif requested_mode == DeepseekMode.r1:
                resolved_id = DeepseekResolvedModel.r1.value
            else:
                resolved_id = auto_model_id

            # Actual DeepSeek API call
            client = DeepseekProvider(
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                model=resolved_id,
            )
            content, tokens_in, tokens_out = await client.invoke(messages)

            cost_usd = estimate_deepseek_cost(resolved_id, tokens_in, tokens_out)
            model_used = resolved_id
            confidence = conf_score

            # Construct routing info for UI transparency
            deepseek_routing_info = DeepseekRoutingInfo(
                requested_mode=requested_mode,
                resolved_model=resolved_id,
                auto_recommended_model=auto_model_id,
                confidence_score=conf_score,
                confidence_label=confidence_label(conf_score),
                confidence_message=reason,
            )

        # ---------------------------------------------------------
        # OTHER PROVIDERS (NOT IMPLEMENTED)
        # ---------------------------------------------------------
        else:
            content = f"[DEMO] Provider {provider.value} not implemented"

    except Exception as ex:
        success = False
        error_code = type(ex).__name__
        content = f"Error: {ex}"
        confidence = 0.0

    # Latency
    latency_ms = int((time.perf_counter() - start) * 1000)

    # Persist invocation log
    await log_invocation(
        db,
        user_id=user.id,
        session_id=session.id,
        router_request_id=rr.id,
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

    return (
        RouterResultItem(
            provider=provider,
            model=model_used,
            profile=profile,
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=float(cost_usd),
            confidence=confidence,
        ),
        deepseek_routing_info,
    )

# ============================================================
#  call_providers: orchestrates base calls + ensemble
# ============================================================

async def call_providers(
    req: RouterChatRequest,
    db: AsyncSession,
    user,
    session,
):
    # Record the router-level request
    rr = AiRouterRequest(
        user_id=user.id,
        session_id=session.id,
        profile=req.profile,
    )
    db.add(rr)
    await db.commit()
    await db.refresh(rr)

    # --- SEQUENTIAL CALLS (no asyncio.gather) ---
    base_results: List[RouterResultItem] = []
    deepseek_meta: DeepseekRoutingInfo | None = None

    for p in req.providers:
        # For DeepSeek, prefer explicit model_hint_map; fallback to deepseek_mode
        if p == Provider.deepseek:
            hint = req.model_hint_map.get(p.value) or req.deepseek_mode.value
            # normalize messages only for DeepSeek so JSON serialization works
            messages_for_provider = _normalize_messages_for_llm(req.messages)
        else:
            hint = req.model_hint_map.get(p.value)
            # keep existing behavior for non-DeepSeek providers
            messages_for_provider = req.messages

        item, meta = await call_single(
            db=db,
            user=user,
            session=session,
            rr=rr,
            provider=p,
            model_hint=hint,
            profile=req.profile,
            messages=messages_for_provider,
        )

        base_results.append(item)
        if meta:
            deepseek_meta = meta

    # No ensemble: single provider or consolidation disabled
    if len(base_results) == 1 or not req.consolidate.enabled:
        final_item = base_results[0]
        return (
            FinalResult(
                content=final_item.content,
                strategy="single_model",
                provider=final_item.provider,
                model=final_item.model,
                estimated_cost_usd=final_item.cost_usd,
                deepseek_routing=deepseek_meta,
            ),
            base_results,
        )

    # Ensemble logic (Gemini as consolidator)
    from app.services.ensemble_service import build_and_call_ensemble

    final_result = await build_and_call_ensemble(
        req=req,
        db=db,
        user=user,
        session=session,
        router_request=rr,
        base_results=base_results,
    )

    # Attach DeepSeek routing info (if any) to the final result as well
    final_result.deepseek_routing = deepseek_meta

    final_result = await build_and_call_ensemble(
        req=req,
        db=db,
        user=user,
        session=session,
        router_request=rr,
        base_results=base_results,
    )

    final_result.deepseek_routing = deepseek_meta

    # ⬇️ Commit ENTIRE transaction (router request + invocations)
    await db.commit()

    return final_result, base_results
