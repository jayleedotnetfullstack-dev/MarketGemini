
# src/marketgemini_router/core/detect.py
from __future__ import annotations
from typing import List, Dict


def auto_profile_for_messages(messages: List[Dict], explicit: str | None) -> str:
    """
    Decide which profile to use.

    - If explicit and not "auto" → respect it.
    - Else look at user text and pick: code / summary / rewrite / factual
    """
    if explicit and explicit != "auto":
        return explicit

    # Concatenate last user message(s)
    user_texts = [m.get("content", "") for m in messages if m.get("role") == "user"]
    text = " ".join(user_texts)[-512:].lower()

    # very simple heuristic — you can tune later
    if any(k in text for k in ["bug", "stack trace", "exception", "c#", "python", "code block"]):
        return "code"
    if any(k in text for k in ["summarize", "summary", "tl;dr", "in bullets", "in 3 points"]):
        return "summary"
    if any(k in text for k in ["rewrite", "rephrase", "improve wording", "make this nicer"]):
        return "rewrite"
    # default
    return "factual"
