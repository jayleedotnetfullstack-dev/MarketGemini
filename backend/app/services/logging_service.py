# backend/app/services/logging_service.py

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import Provider
from app.db.models import AiInvocation

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
    """
    Persist a single model invocation (Gemini, DeepSeek, etc.) into ai_invocations.

    IMPORTANT:
    ---------
    This function **must not commit the DB session**.

    - router_chat() now owns the transaction
    - call_providers() will commit exactly ONE TIME at the end
    - log_invocation() only appends rows to the transaction buffer

    This prevents IllegalStateChangeError caused by committing during flush.
    """

    inv = AiInvocation(
        user_id=user_id,
        session_id=session_id,
        router_request_id=router_request_id,
        provider=provider.value if hasattr(provider, "value") else str(provider),
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

    # Add row to the pending transaction (do NOT commit)
    db.add(inv)

    # Ensure SQLAlchemy assigns PK + prepares row for commit
    # but does NOT finalize the transaction
    await db.flush()
