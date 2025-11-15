from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml


# --- Load router.yml once at startup into global CFG -------------------------

# This file lives at: src/marketgemini_router/core/config.py
# router.yml is at project root: C:\jay\ProjectAI\router.yml
ROOT_DIR = Path(__file__).resolve().parents[1]  # .../src/marketgemini_router/core -> up 3 = project root
CFG_PATH = ROOT_DIR / "router.yml"

with CFG_PATH.open("r", encoding="utf-8") as f:
    CFG: Dict[str, Any] = yaml.safe_load(f)


# --- Helper: rough token estimate -------------------------------------------

def _est_tokens(messages: List[Dict[str, Any]]) -> int:
    text = " ".join(m.get("content", "") for m in messages)
    return max(1, math.ceil(len(text) / 4))


# --- Attach per-profile temperature/top_p into provider config --------------

def _attach_profile_cfg(profile: str, pcfg: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inject only the active profile into provider cfg so adapters
    can read cfg['profiles'][profile] safely.
    """
    global_profiles = cfg.get("profiles", {})
    prof_cfg = global_profiles.get(profile, {"temperature": 0.2, "top_p": 1.0})
    merged = dict(pcfg)
    merged["profiles"] = {profile: prof_cfg}
    return merged


# --- Cost-aware provider selection (messages optional for backward compat) ---

def get_provider_cfg(
    profile: str,
    cfg: Dict[str, Any] | None = None,
    messages: List[Dict[str, Any]] | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Decide which provider to use for this profile.

    - If `messages` is provided → use cost-aware routing with cost_in/cost_out.
    - If `messages` is None → fall back to simple highest-target_share selection.

    Returns: (provider_name, provider_cfg_with_profiles)
    """
    if cfg is None:
        cfg = CFG

    providers = cfg.get("providers", {})
    routing = cfg.get("routing", {})
    target_share = routing.get("target_share", {})

    # If we don't have messages, do simple selection:
    if messages is None:
        # Pick the enabled provider with the highest target_share
        best_name = None
        best_share = -1.0
        best_cfg = None

        for name, pcfg in providers.items():
            if not pcfg.get("enabled", False):
                continue
            share = float(target_share.get(name, 0.0))
            if share > best_share:
                best_share = share
                best_name = name
                best_cfg = pcfg

        if best_name is None or best_cfg is None:
            raise RuntimeError("No enabled providers found in router.yml")

        return best_name, _attach_profile_cfg(profile, best_cfg, cfg)

    # If we DO have messages, estimate tokens and cost per provider:
    est_in = _est_tokens(messages)
    est_out = max(1, est_in // 2)  # simple heuristic

    candidates: List[Tuple[float, float, str, Dict[str, Any]]] = []

    for name, pcfg in providers.items():
        if not pcfg.get("enabled", False):
            continue
        share = float(target_share.get(name, 0.0))
        if share <= 0.0:
            continue

        cin = float(pcfg.get("cost_in", 0.0))
        cout = float(pcfg.get("cost_out", 0.0))

        # Approximate cost per call, using your per-1k token prices
        cost = (cin * est_in + cout * est_out) / 1000.0

        # sort key: (cost ascending, share descending)
        candidates.append((cost, -share, name, pcfg))

    if not candidates:
        # Fallback: first enabled provider
        for name, pcfg in providers.items():
            if pcfg.get("enabled", False):
                return name, _attach_profile_cfg(profile, pcfg, cfg)
        raise RuntimeError("No enabled providers in router.yml")

    candidates.sort(key=lambda x: (x[0], x[1]))
    _, _, best_name, best_cfg = candidates[0]

    return best_name, _attach_profile_cfg(profile, best_cfg, cfg)
