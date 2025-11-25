import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import text

# Load .env file from backend folder
load_dotenv()

DATABASE_URL = os.getenv("POSTGRES_URL")
if not DATABASE_URL:
    raise RuntimeError("POSTGRES_URL not set in environment (.env)")

# echo=True prints SQL (great for debugging)
engine = create_async_engine(DATABASE_URL, echo=True)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

class Base(DeclarativeBase):
    """Base for ORM models."""
    pass

async def get_db() -> AsyncSession:
    """FastAPI dependency to get an async DB session."""
    async with SessionLocal() as session:
        yield session

async def test_connection():
    """Simple debug function to test DB connectivity at startup."""
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        value = result.scalar_one()
        print("✅ DB test result:", value)
