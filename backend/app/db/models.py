# backend/app/db/models.py

import uuid

from sqlalchemy import (
    Column,
    String,
    Boolean,
    Integer,
    Numeric,
    ForeignKey,
    TIMESTAMP,
    text,
    UniqueConstraint,  # <-- NEW
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String, unique=True, nullable=False)
    display_name = Column(String, nullable=False)
    email = Column(String)

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    last_login_at = Column(TIMESTAMP(timezone=True))

    sessions = relationship("Session", back_populates="user")

    # NEW: one user can have many external identities (Google, Apple, MSFT, etc.)
    identities = relationship(
        "UserIdentity",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String)
    # keep this:
    external_id = Column(String, nullable=True, index=True)

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    last_seen_at = Column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    is_active = Column(Boolean, nullable=False, server_default=text("TRUE"))

    user = relationship("User", back_populates="sessions")
    router_requests = relationship("AiRouterRequest", back_populates="session")


class AiRouterRequest(Base):
    __tablename__ = "ai_router_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    profile = Column(String)

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    user = relationship("User")
    session = relationship("Session", back_populates="router_requests")
    invocations = relationship("AiInvocation", back_populates="router_request")


class AiInvocation(Base):
    __tablename__ = "ai_invocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    router_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_router_requests.id"),
        nullable=True,
    )

    # e.g. 'gemini', 'openai', 'deepseek'
    provider = Column(String, nullable=False)
    # concrete model ID, e.g. 'gemini-2.0-flash', 'deepseek-r1'
    model = Column(String, nullable=False)
    # logical profile like 'factual', 'summary', 'ensemble'
    profile = Column(String, nullable=False)

    confidence = Column(Numeric(4, 3))
    tokens_in = Column(Integer)
    tokens_out = Column(Integer)
    tokens_total = Column(Integer)
    cost_usd = Column(Numeric(10, 6))
    latency_ms = Column(Integer)

    success = Column(Boolean, nullable=False)
    error_code = Column(String)

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    router_request = relationship("AiRouterRequest", back_populates="invocations")


# NEW: external login identity table
class UserIdentity(Base):
    """
    External login identity representing one authenticated identity
    from an IdP (Google, Apple, MSFT, DeepSeek, Local, etc.)

    Rules:
      - provider: "google", "apple", "msft", "deepseek", "local"
      - provider_sub: stable user ID from that provider
      - A single User can have many identities.
      - (provider, provider_sub) is globally unique.
    """

    __tablename__ = "user_identities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # FK → users.id
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Example: "google", "apple", "msft", "deepseek", "local"
    provider = Column(String, nullable=False)

    # Example: Google: sub; Apple: sub; MSFT: oid; Local: username/email
    provider_sub = Column(String, nullable=False)

    # Optional user fields mirrored from IdP
    email = Column(String, nullable=True)
    display_name = Column(String, nullable=True)

    created_at = Column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )
    last_used_at = Column(
        TIMESTAMP(timezone=True),
        server_default=text("NOW()"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_sub",
            name="uq_user_identity_provider_sub",
        ),
    )

    # Relationship back into User.identities
    user = relationship("User", back_populates="identities")

