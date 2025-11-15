# src/marketgemini_router/core/reward.py

from __future__ import annotations
from typing import Dict

from marketgemini_router.core.config import CFG


def calc_cost(provider: str, tokens_in: int, tokens_out: int) -> float:
    """
    Compute approximate USD cost of a call based on router.yml.

    router.yml expects per-1K token prices:

      providers:
        gemini:
          cost_in: 0.10    # $/1K input tokens
          cost_out: 0.40   # $/1K output tokens
        openai:
          cost_in: 0.15
          cost_out: 0.60
        deepseek:
          cost_in: 0.14
          cost_out: 0.28

    This function uses:

      cost = (cost_in * tokens_in + cost_out * tokens_out) / 1000.0
    """
    providers: Dict[str, Dict] = CFG.get("providers", {})
    pcfg = providers.get(provider, {})

    cin = float(pcfg.get("cost_in", 0.0))
    cout = float(pcfg.get("cost_out", 0.0))

    if tokens_in < 0:
        tokens_in = 0
    if tokens_out < 0:
        tokens_out = 0

    cost = (cin * tokens_in + cout * tokens_out) / 1000.0
    return round(cost, 6)  # keep a nice small float for logging/UI
