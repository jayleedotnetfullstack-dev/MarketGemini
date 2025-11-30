# backend/app/router_chat.py
import logging
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.core import RouterChatRequest, RouterChatResponse
from app.db.session import get_db
from app.services.session_service import (
    get_current_user,
    get_or_create_session,
    get_or_create_user_from_identity,
    UserIdentityInfo,
)
from app.services.call_service import call_providers

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------
# /v1/router/digest  – simple intent classifier stub
# ---------------------------------------------------------


class DigestMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class DigestRequest(BaseModel):
    user_id: str
    session_id: str
    messages: List[DigestMessage]


class DigestResponse(BaseModel):
    intent: str


class WhoAmIResponse(BaseModel):
    user_id: str
    external_id: str
    display_name: str
    email: Optional[str] = None
    primary_identity: Optional[Dict[str, Any]] = None


@router.get("/v1/auth/whoami", response_model=WhoAmIResponse)
async def whoami() -> WhoAmIResponse:
    """
    Debug endpoint: shows which internal User + primary identity
    the backend is using for the current request.

    For now this uses the dev identity stub (provider='local', provider_sub='dev-user-1').
    Later, the stub will be replaced by real Google/Apple/MSFT/DeepSeek login.
    """
    from sqlalchemy import select
    from app.db.models import UserIdentity

    # 1) Get DB session (same pattern as router_chat)
    db = None
    try:
        async for db_session in get_db():
            db = db_session
            break
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc!r}")

    if db is None:
        raise HTTPException(status_code=500, detail="db_not_available")

    # 2) Resolve current user via identity mapping
    try:
        user = await get_current_user(db=db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"get_current_user_error: {exc!r}")

    # 3) Load one identity row explicitly (no lazy relationship to avoid MissingGreenlet)
    ident_stmt = (
        select(UserIdentity)
        .where(UserIdentity.user_id == user.id)
        .order_by(UserIdentity.created_at.asc())
        .limit(1)
    )
    ident_result = await db.execute(ident_stmt)
    ui = ident_result.scalar_one_or_none()

    primary_identity: Optional[Dict[str, Any]] = None
    if ui is not None:
        primary_identity = {
            "provider": ui.provider,
            "provider_sub": ui.provider_sub,
            "email": ui.email,
            "display_name": ui.display_name,
        }

    return WhoAmIResponse(
        user_id=str(user.id),
        external_id=user.external_id,
        display_name=user.display_name,
        email=user.email,
        primary_identity=primary_identity,
    )


@router.post("/v1/router/digest", response_model=DigestResponse)
async def router_digest(req: DigestRequest) -> DigestResponse:
    """
    LLM-based intent classifier using Gemini.
    """

    # Import locally to keep startup clean
    from app.providers.gemini_provider import call_gemini_api
    import json

    # Build a compact conversation transcript
    convo_lines = []
    for m in req.messages:
        convo_lines.append(f"{m.role}: {m.content}")
    convo_text = "\n".join(convo_lines)

    # Clean multi-line classifier prompt
    classifier_prompt = f"""
You are an intent classifier for a developer chat UI.

Read the conversation below and choose **exactly ONE** intent label from:

  - bug_report
  - explanation
  - summary
  - general

Return strictly JSON **only**, in the following format:
{{
  "intent": "bug_report"
}}

Conversation:
{convo_text}
"""

    # Wrap in a chat-format message
    messages_for_gemini = [
        {"role": "user", "content": classifier_prompt}
    ]

    # Default if everything fails
    intent = "general"

    try:
        content, tokens_in, tokens_out, model_used = await call_gemini_api(
            messages_for_gemini,
            model_hint="gemini-2.5-flash",
        )
    except Exception:
        return DigestResponse(intent=intent)

    # Try to parse JSON object from model output
    text = content.strip()
    try:
        # naive bracket extractor
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            block = text[start:end + 1]
            data = json.loads(block)
            candidate = str(data.get("intent", "")).lower()
            if candidate in {"bug_report", "explanation", "summary", "general"}:
                intent = candidate
    except Exception:
        pass

    return DigestResponse(intent=intent)


@router.post("/v1/router/chat", response_model=RouterChatResponse)
async def router_chat(req: RouterChatRequest) -> Dict[str, Any]:
    """
    Phase 2+4 baseline (typed version):
    - FastAPI surface: req: RouterChatRequest -> RouterChatResponse
      (no Depends, no SQLAlchemy types in the signature)
    - Inside:
      * req is already validated by FastAPI/Pydantic
      * Get DB session via get_db()
      * Resolve current user:
          - if req.debug_identity is provided, use that identity
          - otherwise, use get_current_user(dev stub for now)
      * Get or create session via get_or_create_session(...)
      * Call call_providers(...)
      * Return RouterChatResponse (typed), or fallback dict if something
        goes wrong in the diagnostic schema-check path.

    STEP1 additions (earlier):
      * Log basic request info (session_id/profile/providers).
      * Return extra metadata fields: status, session_id, user_id
        in the fallback path.

    STEP2 additions:
      * Bubble up provider/model/strategy/estimated_cost_usd
        from final_result to top-level for easier UI / debugging
        in the fallback path.

    STEP3 additions:
      * Soft schema self-check using RouterChatResponse (diagnostic only,
        never affects response; errors are just logged).

    Phase 4 additions:
      * Support dev-only identity override via req.debug_identity.
    """

    # STEP1: basic debug logging of the validated request
    try:
        providers_list = [p.value for p in req.providers]
    except Exception:
        providers_list = []
    logger.info(
        "router_chat: session_id=%s profile=%s providers=%s deepseek_mode=%s",
        getattr(req, "session_id", None),
        getattr(req, "profile", None),
        providers_list,
        getattr(getattr(req, "deepseek_mode", None), "value", None),
    )

    # 1.5) Phase 4: optional debug_identity override
    identity_override: Optional[UserIdentityInfo] = None
    if getattr(req, "debug_identity", None):
        try:
            identity_override = UserIdentityInfo(**req.debug_identity)
            logger.info(
                "router_chat: using debug_identity provider=%s sub=%s email=%s",
                identity_override.provider,
                identity_override.provider_sub,
                identity_override.email,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400,
                detail=f"debug_identity_validation_error: {exc!r}",
            )

    # 2) Manually get an AsyncSession from get_db()
    db = None
    try:
        async for db_session in get_db():
            db = db_session
            break
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc!r}")

    if db is None:
        raise HTTPException(status_code=500, detail="db_not_available")

    # 3) Get current user
    #    - If debug_identity override is present, use it to resolve the user
    #    - Otherwise, fall back to existing dev stub in get_current_user()
    try:
        if identity_override is not None:
            user = await get_or_create_user_from_identity(db=db, identity=identity_override)
        else:
            user = await get_current_user(db=db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"get_current_user_error: {exc!r}")

    # 4) Get or create session row in DB
    try:
        user_id = str(getattr(user, "id", ""))
        session = await get_or_create_session(
            db=db,
            user_id=user_id,
            session_external_id=req.session_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"session_error: {exc!r}")

    # 5) Call providers orchestrator
    try:
        final_result, base_results = await call_providers(
            req=req,
            db=db,
            user=user,
            session=session,
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"call_providers_error: {exc!r}")

    # 6) Convert any Pydantic models to plain dicts for the fallback response
    def to_dict(obj: Any) -> Any:
        if obj is None:
            return None
        if isinstance(obj, dict):
            return obj
        if hasattr(obj, "model_dump"):  # Pydantic v2
            return obj.model_dump()
        if hasattr(obj, "dict"):        # Pydantic v1
            return obj.dict()
        return obj

    final_dict = to_dict(final_result)
    provider = final_dict.get("provider")
    model = final_dict.get("model")
    strategy = final_dict.get("strategy")
    estimated_cost_usd = final_dict.get("estimated_cost_usd")

    # STEP3: soft schema self-check (diagnostic only)
    typed_response: Optional[RouterChatResponse] = None

    try:
        # Build the typed response from the *original* objects
        typed_response = RouterChatResponse(
            final=final_result,
            results=base_results,
        )

        print(
            "[router_chat] RouterChatResponse schema check OK:",
            type(typed_response.final).__name__ if typed_response.final else None,
            "results_count=",
            len(typed_response.results or []),
        )

    except Exception as exc:
        print("[router_chat] RouterChatResponse schema check FAILED:", repr(exc))
        # We won't fail the request; we’ll just fall back to the manual dict.

    # STEP4: Return JSON
    # Prefer the typed RouterChatResponse payload if it was built successfully;
    # otherwise, fall back to the previous manual structure.
    if typed_response is not None:
        # Let FastAPI/pydantic handle serialization
        return typed_response

    # Fallback: old behavior (what you currently have working)
    return {
        "final": to_dict(final_result),
        "results": [to_dict(r) for r in base_results],
        "meta": {
            "provider": provider,
            "model": model,
            "strategy": strategy,
            "estimated_cost_usd": estimated_cost_usd,
            "user_id": str(getattr(user, "id", "")),
            "session_id": getattr(req, "session_id", None),
        },
    }
