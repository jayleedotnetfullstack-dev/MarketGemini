# backend/app/db/__init__.py

"""
Lightweight DB package init.

We don't re-export models here anymore to avoid circular imports.
Other modules should import models directly from app.db.models.
"""

from .session import engine, Base, get_db, test_connection

__all__ = ["engine", "Base", "get_db", "test_connection"]
