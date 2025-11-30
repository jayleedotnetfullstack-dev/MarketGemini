import asyncio

from app.db.session import engine, Base
from app.db import models  # ensure model classes are registered


async def init_models():
    """
    Creates all tables defined in SQLAlchemy models.
    Safe to run multiple times due to CREATE IF NOT EXISTS behavior.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Allows:
#   python -m app.db.init_db
if __name__ == "__main__":
    asyncio.run(init_models())
