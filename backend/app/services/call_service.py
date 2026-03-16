import time
import asyncio
from typing import Any, Dict, List, Tuple, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import (
    Provider,
    RouterChatRequest,
    RouterResultItem,
    FinalResult,
    DeepseekMode,
    DeepseekRoutingInfo,
)

from app.schemas.core import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL

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

from app.config.providers_loader import get_provider_version
import asyncio

async def call_providers(tasks):
    results = await asyncio.gather(*tasks)
    return results

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
#  Single provider call (CONFIG-DRIVEN)
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
    temperature: Optional[float],
) -> Tuple[RouterResultItem, DeepseekRoutingInfo | None]:

    start = time.perf_counter()

    # -------------------------------
    # Defaults
    # -------------------------------
    tokens_in = 0
    tokens_out = 0
    cost_usd = 0.0
    model_used = model_hint or "unknown"
    confidence = 0.5
    content = ""
    success = True
    error_code = None
    deepseek_routing_info: DeepseekRoutingInfo | None = None

    if temperature is None:
        temperature = 0.4

    try:
        # =====================================================
        # GEMINI
        # =====================================================
        if provider == Provider.gemini:

            # model_hint is the VERSION id (e.g. "2.0-flash")
            version_cfg = get_provider_version("gemini", model_hint)

            model_id = version_cfg["id"]
            base_url = version_cfg["base_url"]

            content, tokens_in, tokens_out, model_used = await call_gemini_api(
                messages,
                model_hint=model_id,
                temperature=temperature,
            )

            cost_usd = 0.0
            confidence = 0.88


        # =====================================================
        # DEEPSEEK
        # =====================================================
        elif provider == Provider.deepseek:

            last_prompt = extract_prompt(messages) or ""
            if not last_prompt.strip():
                raise ValueError("DeepSeek prompt is empty")

            # --------------------------------------------
            # 1. Classifier recommendation
            # --------------------------------------------
            auto_model_enum, conf_score, reason = classify_deepseek_model(last_prompt)
            auto_version_id = auto_model_enum.value  # e.g. "chat" | "r1"

            # --------------------------------------------
            # 2. Requested version from UI
            # --------------------------------------------
            selected_version = model_hint or DeepseekMode.auto.value

            if selected_version == DeepseekMode.auto.value:
                version_id = auto_version_id
            else:
                version_id = selected_version

            # --------------------------------------------
            # 3. Resolve from providers.json
            # --------------------------------------------
            version_cfg = get_provider_version("deepseek", version_id)

            model_id = version_cfg["id"]
            base_url = version_cfg["base_url"]

            print("DEBUG DeepSeek version:", version_id)
            print("DEBUG DeepSeek model:", model_id)
            print("DEBUG DeepSeek base_url:", base_url)

            # --------------------------------------------
            # 4. Strict message format
            # --------------------------------------------
            messages_for_provider = [
                {"role": "user", "content": last_prompt.strip()}
            ]

            # --------------------------------------------
            # 5. Call DeepSeek API
            # --------------------------------------------
            client = DeepseekProvider(
                api_key=DEEPSEEK_API_KEY,
                model=model_id,
                base_url=base_url,
            )

            content, tokens_in, tokens_out = await client.invoke(
                messages_for_provider,
                temperature=temperature,
            )

            cost_usd = estimate_deepseek_cost(
                model_id,
                tokens_in,
                tokens_out,
            )

            model_used = model_id
            confidence = conf_score

            # --------------------------------------------
            # 6. Routing transparency
            # --------------------------------------------
            deepseek_routing_info = DeepseekRoutingInfo(
                requested_mode=DeepseekMode(selected_version)
                if selected_version in DeepseekMode._value2member_map_
                else DeepseekMode.auto,
                resolved_model=model_id,
                auto_recommended_model=auto_version_id,
                confidence_score=conf_score,
                confidence_label=confidence_label(conf_score),
                confidence_message=reason,
            )

        # =====================================================
        # OTHER PROVIDERS
        # =====================================================
        else:
            content = f"[DEMO] Provider {provider.value} not implemented"

    except Exception as ex:
        success = False
        error_code = type(ex).__name__
        content = f"Error: {ex}"
        confidence = 0.0

    # =====================================================
    # Latency
    # =====================================================
    latency_ms = int((time.perf_counter() - start) * 1000)

    # =====================================================
    # Persist invocation log
    # =====================================================
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

    # =====================================================
    # Return result
    # =====================================================
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
#  Call multiple providers / versions (VERSION-AWARE)
# ============================================================

async def call_providers(
    db: AsyncSession,
    *,
    user,
    session,
    rr: AiRouterRequest,
    provider_selections: list,   # [{id: "deepseek", versions: [...]}, ...]
    profile: str,
    messages,
    temperature: Optional[float],
) -> Tuple[List[RouterResultItem], DeepseekRoutingInfo | None]:

    tasks = []
    deepseek_routing_info: DeepseekRoutingInfo | None = None

    # --------------------------------------------------------
    # Expand provider + versions
    # --------------------------------------------------------
    for selection in provider_selections:

        provider_id = selection.get("id")
        versions = selection.get("versions") or []

        try:
            provider_enum = Provider(provider_id)
        except ValueError:
            print(f"Unknown provider: {provider_id}")
            continue

        # -----------------------------------------------
        # If no versions provided, fallback to default
        # -----------------------------------------------
        if not versions:
            versions = [None]

        for version in versions:

            tasks.append(
                call_single(
                    db=db,
                    user=user,
                    session=session,
                    rr=rr,
                    provider=provider_enum,
                    model_hint=version,   # version ID passed here
                    profile=profile,
                    messages=messages,
                    temperature=temperature,
                )
            )

    # --------------------------------------------------------
    # Execute in parallel
    # --------------------------------------------------------
    results = await asyncio.gather(*tasks)

    router_items: List[RouterResultItem] = []

    for result_item, ds_info in results:
        router_items.append(result_item)

        # Only keep first DeepSeek routing info (optional)
        if ds_info and deepseek_routing_info is None:
            deepseek_routing_info = ds_info

    return router_items, deepseek_routing_info
