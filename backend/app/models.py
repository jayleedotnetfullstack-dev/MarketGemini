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
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from .db import Base

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


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String)
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

    provider = Column(String, nullable=False)    # 'gemini', 'openai', 'deepseek'
    model = Column(String, nullable=False)
    profile = Column(String, nullable=False)     # 'factual', 'summary', 'ensemble'

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
