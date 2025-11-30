import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

# ------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------
load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_URL")
if not DATABASE_URL:
    raise RuntimeError("POSTGRES_URL not set in environment (.env)")


# ------------------------------------------------------------
# Create async SQLAlchemy engine
# ------------------------------------------------------------
# echo=True prints SQL statements (optional for debugging)
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
)


# ------------------------------------------------------------
# Async session factory
# ------------------------------------------------------------
SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# ------------------------------------------------------------
# Base class for ORM models
# ------------------------------------------------------------
class Base(DeclarativeBase):
    """Base for all ORM models."""
    pass


# ------------------------------------------------------------
# FastAPI DB dependency
# ------------------------------------------------------------
async def get_db() -> AsyncSession:
    """
    Provides an async SQLAlchemy session for FastAPI.
    Ensures proper cleanup after request.
    """
    async with SessionLocal() as session:
        yield session


# ------------------------------------------------------------
# Optional: startup connectivity check
# ------------------------------------------------------------
async def test_connection():
    """
    Optional function to verify DB connectivity during startup.
    Call from main.py's startup event if desired.
    """
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        value = result.scalar_one()
        print("✅ DB connection OK:", value)
