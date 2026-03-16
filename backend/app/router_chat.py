# backend/app/router_chat.py
import logging
import uuid
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
from app.schemas.digest import DigestResponse

from app.schemas import DigestRequest
from app.services.digest_service import run_digest

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------
# Helper: DeepSeek model selection
# ---------------------------------------------------------
def select_deepseek_model(req: RouterChatRequest) -> str:
    mode = (getattr(req, "deepseek_mode", "auto") or "auto").lower()
    chat_model = "deepseek-chat"
    reasoning_model = "deepseek-reasoner"

    if mode == "chat":
        return chat_model
    if mode == "reasoning":
        return reasoning_model

    if req.profile in ("code", "analysis", "research"):
        return reasoning_model
    return chat_model


# ---------------------------------------------------------
# Temperature policy layer
# ---------------------------------------------------------
def resolve_temperature(
    default: float = 0.4,
    user_override: Optional[float] = None,
    profile: Optional[str] = None,
    intent: Optional[str] = None,
) -> float:
    """
    Determine the temperature to use for a request.
    Order of precedence:
    1. User override
    2. Profile/intent rules
    3. Default
    """
    if user_override is not None:
        return max(0.0, min(user_override, 1.0))  # clamp 0-1

    # Simple rules: higher temperature for creative intents
    if intent in ("summary", "explanation"):
        return 0.6
    if profile in ("code", "analysis"):
        return 0.3

    return default


# ---------------------------------------------------------
# /v1/router/digest – intent classifier + confidence + suggestions
# ---------------------------------------------------------
class DigestMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class DigestRequest(BaseModel):
    user_id: str
    session_id: str
    messages: List[DigestMessage]
    temperature: Optional[float] = None  # optional user override


class WhoAmIResponse(BaseModel):
    user_id: str
    external_id: str
    display_name: str
    email: Optional[str] = None
    primary_identity: Optional[Dict[str, Any]] = None


@router.get("/v1/auth/whoami", response_model=WhoAmIResponse)
async def whoami() -> WhoAmIResponse:
    from sqlalchemy import select
    from app.db.models import UserIdentity

    db = None
    try:
        async with get_db() as db_session:  # ✅ correct syntax
            db = db_session
            # no 'break' needed
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc!r}")

    if db is None:
        raise HTTPException(status_code=500, detail="db_not_available")

    try:
        user = await get_current_user(db=db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"get_current_user_error: {exc!r}")

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
    raw_prompt = req.messages[-1].content.strip()
    digest_result = await run_digest(
        raw_prompt=raw_prompt,
        messages=req.messages,
        temperature=getattr(req, "temperature", None)
    )
    
    return digest_result

# ---------------------------------------------------------
# /v1/router/chat – full router
# ---------------------------------------------------------
@router.post("/v1/router/chat", response_model=RouterChatResponse)
async def router_chat(req: RouterChatRequest) -> Any:
    try:
        req.id = req.session_id or str(uuid.uuid4())
        providers_list = [p.value for p in req.providers]
    except Exception:
        providers_list = []

    deepseek_mode_value = getattr(req, "deepseek_mode", None)
    logger.info(
        "router_chat: session_id=%s profile=%s providers=%s deepseek_mode=%s",
        getattr(req, "session_id", None),
        getattr(req, "profile", None),
        providers_list,
        deepseek_mode_value,
    )

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

    db = None
    try:
        async with get_db() as session:
            db = session
            # use db/session here if needed
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"db_error: {exc!r}")

    if db is None:
        raise HTTPException(status_code=500, detail="db_not_available")

    try:
        if identity_override is not None:
            user = await get_or_create_user_from_identity(db=db, identity=identity_override)
        else:
            user = await get_current_user(db=db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"get_current_user_error: {exc!r}")

    # Convert user_id from string to UUID (must exist in users table)
    try:
        user_id = uuid.UUID(str(getattr(user, "id", "")))  # safe UUID
    except ValueError:
        raise HTTPException(status_code=400, detailA="invalid user_id, must be UUID")
    
    try:
        # Keep session_external_id as string, do NOT assign to Session.id
        session = await get_or_create_session(
            db=db,
            user_id=user_id,                     # UUID object
            session_external_id=req.session_id   # string like "router-lab-session-1"
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"session_error: {exc!r}")

    # -----------------------------
    # Resolve temperature for this request
    # -----------------------------
    request_temperature = resolve_temperature(
        user_override=getattr(req, "temperature", None),
        profile=getattr(req, "profile", None),
    )

    # -----------------------------
    # Call providers orchestrator
    # -----------------------------
    # -----------------------------
# Call providers orchestrator
# -----------------------------
    try:
        # -----------------------------
        # Generate .id for RouterChatRequest
        # -----------------------------
        if not hasattr(req, "id"):
            setattr(req, "id", getattr(req, "session_id", str(uuid.uuid4())))
        router_items, _ = await call_providers(
            db=db,
            user=user,
            session=session,
            rr=req,
            provider_selections=[{"id": p.value, "versions": []} for p in req.providers],
            profile=req.profile,
            messages=req.messages,
            temperature=request_temperature,
        )

        final_result = router_items[0] if router_items else None
        base_results = router_items
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"call_providers_error: {exc!r}")

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

    final_dict = to_dict(final_result) or {}
    provider = final_dict.get("provider")
    model = final_dict.get("model")
    strategy = final_dict.get("strategy")
    estimated_cost_usd = final_dict.get("estimated_cost_usd")

    typed_response: Optional[RouterChatResponse] = None
    try:
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

    if typed_response is not None:
        return typed_response

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
            "temperature": request_temperature,  # include resolved temperature
        },
    }
