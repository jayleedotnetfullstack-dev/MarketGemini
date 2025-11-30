# backend/app/services/session_service.py

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import BaseModel

from app.db.models import User, Session, UserIdentity


class UserIdentityInfo(BaseModel):
    """
    Simple Pydantic model describing an external identity
    (Google, Apple, MSFT, DeepSeek, local, etc.).
    """
    provider: str            # e.g. "google", "apple", "msft", "deepseek", "local"
    provider_sub: str        # stable ID from that provider (e.g., 'sub', 'oid')
    email: Optional[str] = None
    display_name: Optional[str] = None


async def get_or_create_user_from_identity(
    db: AsyncSession,
    identity: UserIdentityInfo,
) -> User:
    """
    Map an external identity to an internal User.

    1) Look for existing UserIdentity(provider, provider_sub)
    2) If found -> return linked User (optionally updating email/display_name)
    3) If not found -> create new User + UserIdentity row

    IMPORTANT: we never touch ui.user (lazy relationship) to avoid MissingGreenlet.
    We always load User explicitly via SELECT.
    """

    # 1) Try to find an existing identity row
    stmt = (
        select(UserIdentity)
        .where(
            UserIdentity.provider == identity.provider,
            UserIdentity.provider_sub == identity.provider_sub,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    ui: UserIdentity | None = result.scalar_one_or_none()

    if ui is not None:
        # Explicitly load the User by user_id (NO ui.user lazy access)
        user_result = await db.execute(
            select(User).where(User.id == ui.user_id)
        )
        user: User | None = user_result.scalar_one_or_none()

        if user is None:
            # Extremely rare: identity exists but user row missing.
            # Treat as orphaned; create a new user and reattach.
            external_id = f"{identity.provider}:{identity.provider_sub}"
            display_name = identity.display_name or identity.provider_sub

            user = User(
                external_id=external_id,
                display_name=display_name,
                email=identity.email,
            )
            db.add(user)
            await db.flush()  # get user.id

            ui.user_id = user.id
        # Optionally update cached email / display_name on UserIdentity
        updated = False
        if identity.email and ui.email != identity.email:
            ui.email = identity.email
            updated = True
        if identity.display_name and ui.display_name != identity.display_name:
            ui.display_name = identity.display_name
            updated = True

        ui.last_used_at = datetime.now(timezone.utc)
        updated = True

        if updated:
            await db.commit()
            await db.refresh(user)

        return user

    # 2) No identity found: create a new User and link it
    external_id = f"{identity.provider}:{identity.provider_sub}"
    display_name = identity.display_name or identity.provider_sub

    user = User(
        external_id=external_id,
        display_name=display_name,
        email=identity.email,
    )
    db.add(user)
    await db.flush()  # get user.id

    ui = UserIdentity(
        user_id=user.id,
        provider=identity.provider,
        provider_sub=identity.provider_sub,
        email=identity.email,
        display_name=display_name,
    )
    db.add(ui)

    await db.commit()
    await db.refresh(user)

    return user


async def get_current_user(db: AsyncSession) -> User:
    """
    Central entry point for 'who is the current user?'.

    Phase 4 behavior:
      - Use a dev stub to produce an external identity (provider + provider_sub)
      - Map that identity to an internal User via get_or_create_user_from_identity
      - Return the User ORM object

    Later, only _dev_identity_stub() needs to change to read a real token.
    """
    identity = await _dev_identity_stub()
    user = await get_or_create_user_from_identity(db, identity)
    return user


async def get_or_create_session(
    db: AsyncSession,
    user_id: UUID,
    session_external_id: str,
) -> Session:
    """
    Look up a Session row for (user_id, external_id=session_external_id).
    If it doesn't exist, create one. Also updates last_seen_at.
    """
    result = await db.execute(
        select(Session).where(
            Session.user_id == user_id,
            Session.external_id == session_external_id,
        )
    )
    session: Session | None = result.scalar_one_or_none()
    if session:
        session.last_seen_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(session)
        return session

    session = Session(
        id=uuid4(),
        user_id=user_id,
        external_id=session_external_id,
        title=f"Session {session_external_id}",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


# Dev-only stub: pretend we already authenticated the user externally
async def _dev_identity_stub() -> UserIdentityInfo:
    """
    Development stub for an external identity.

    Later this will be replaced by:
      - reading/verifying a JWT or OAuth token
      - extracting provider, provider_sub, email, display_name
    For now, it just returns a stable fake identity.
    """
    return UserIdentityInfo(
        provider="local",              # e.g. "google", "apple", "msft", "deepseek"
        provider_sub="dev-user-1",     # stable ID from that provider
        email="local-dev@example.com",
        display_name="Local Dev User",
    )
