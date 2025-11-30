# backend/app/services/identity_service.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, UserIdentity
from app.schemas.auth import UserIdentityInfo


async def get_or_create_user_from_identity(
    db: AsyncSession,
    identity: UserIdentityInfo,
) -> User:
    """
    Core helper: given an external identity (Google / Apple / MSFT / etc.),
    return the internal User row, creating both User and UserIdentity if needed.

    Rules:
      1. If we already have a UserIdentity(provider, provider_sub) -> return that User.
      2. Else, if email is present and already used by a User, link identity to that User.
      3. Else, create a new User + UserIdentity.
    """

    # 1) Look up by (provider, provider_sub)
    stmt = select(UserIdentity).where(
        UserIdentity.provider == identity.provider,
        UserIdentity.provider_sub == identity.provider_sub,
    )
    result = await db.execute(stmt)
    existing_identity: Optional[UserIdentity] = result.scalar_one_or_none()

    if existing_identity:
        # Update last_used_at and possibly email / display name
        existing_identity.last_used_at = datetime.now(timezone.utc)

        if identity.email and not existing_identity.email:
            existing_identity.email = str(identity.email)
        if identity.display_name and not existing_identity.display_name:
            existing_identity.display_name = identity.display_name

        # Load the linked user
        user = await db.get(User, existing_identity.user_id)

        # Optionally keep user fields fresh (only filling blanks)
        if user:
            if identity.display_name and not user.display_name:
                user.display_name = identity.display_name
            if identity.email and not user.email:
                user.email = str(identity.email)

        await db.commit()
        if user:
            await db.refresh(user)
            return user

        # Safety: if somehow user missing, fall through and recreate
        # a User for this identity.

    # 2) No existing identity; try to find User by email (if present)
    user: Optional[User] = None
    if identity.email:
        stmt = select(User).where(User.email == str(identity.email))
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

    # 3) If no User, create a new one
    if user is None:
        external_id_value = f"{identity.provider}:{identity.provider_sub}"

        user = User(
            id=uuid.uuid4(),
            external_id=external_id_value,
            display_name=identity.display_name
            or (str(identity.email) if identity.email else external_id_value),
            email=str(identity.email) if identity.email else None,
        )
        db.add(user)
        # flush to get user.id populated without committing yet
        await db.flush()

    # 4) Create the UserIdentity row pointing to this User
    new_identity = UserIdentity(
        id=uuid.uuid4(),
        user_id=user.id,
        provider=identity.provider,
        provider_sub=identity.provider_sub,
        email=str(identity.email) if identity.email else None,
        display_name=identity.display_name,
    )
    db.add(new_identity)

    # Single commit at the end
    await db.commit()
    await db.refresh(user)
    return user
