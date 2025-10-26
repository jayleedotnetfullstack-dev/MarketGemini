# src/marketgemini_backend/app/core/logging.py
from __future__ import annotations
import logging
import os

_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR":    logging.ERROR,
    "WARNING":  logging.WARNING,
    "INFO":     logging.INFO,
    "DEBUG":    logging.DEBUG,
    "NOTSET":   logging.NOTSET,
}

def _level_from_env(var: str, default: str = "INFO") -> int:
    val = (os.getenv(var, default) or "").strip().upper()
    return _LEVELS.get(val, _LEVELS[default])

def setup_logging() -> None:
    """
    Configure root logging once. Idempotent.
    LOG_LEVEL controls verbosity (default INFO).
    """
    root = logging.getLogger()
    if root.handlers:
        # already configured (pytest, uvicorn, etc.)
        root.setLevel(_level_from_env("LOG_LEVEL", "INFO"))
        return

    level = _level_from_env("LOG_LEVEL", "INFO")
    fmt = "%(asctime)s.%(msecs)03d %(levelname)-8s %(name)s %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%S"

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))

    root.setLevel(level)
    root.addHandler(handler)
