# src/marketgemini_backend/app/core/trace.py
from __future__ import annotations
import logging
import os
import time
from typing import Any, Mapping

from .logging import setup_logging

# Ensure logging is configured before we emit anything
setup_logging()

AUTH_TRACE = (os.getenv("AUTH_TRACE", "")).lower() in ("1", "true", "yes", "on")
_log = logging.getLogger("marketgemini.auth")

def _fmt_kv(d: Mapping[str, Any]) -> str:
    return " ".join(f"{k}={d[k]}" for k in d)

def auth_trace(event: str, **kv: Any) -> None:
    """
    Emit a single-line structured log ONLY when AUTH_TRACE=true.
    Example:
      [auth] security.selector ts=... mode=OIDC required_scope=series:read
    """
    if not AUTH_TRACE:
        return
    kv2 = {"ts": int(time.time()), **kv}
    _log.info("[auth] %s %s", event, _fmt_kv(kv2))
