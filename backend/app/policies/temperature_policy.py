# backend/app/policies/temperature_policy.py

from typing import Optional

POLICY_VERSION = "v1.0"

def resolve_temperature(
    *,
    provider: str,
    profile: str,
    intent: Optional[str],
    user_temperature: Optional[float],
) -> tuple[float, str]:
    """
    Resolve final temperature based on routing policy.
    Returns (resolved_temperature, policy_version)
    """

    # 1️⃣ User override (if explicitly allowed)
    if user_temperature is not None:
        return float(user_temperature), POLICY_VERSION

    # 2️⃣ Profile-based defaults
    if profile in ("code", "bugfix"):
        return 0.2, POLICY_VERSION

    if profile in ("summary", "digest"):
        return 0.3, POLICY_VERSION

    # 3️⃣ Intent-based tuning
    if intent == "bug_report":
        return 0.2, POLICY_VERSION

    if intent == "explanation":
        return 0.5, POLICY_VERSION

    # 4️⃣ Provider defaults
    if provider == "deepseek":
        return 0.6, POLICY_VERSION

    # 5️⃣ Safe fallback
    return 0.4, POLICY_VERSION
