# backend/app/routing/prompt_helpers.py

from typing import Any, List


def extract_prompt(messages: List[Any]) -> str:
    """
    Extract the "user prompt" from a messages list.

    Supports:
    - Pydantic Message objects with .content
    - dicts with "content" key
    - raw strings as a fallback

    Currently we just take the last message, assuming that's the
    latest user input the router is classifying.
    """
    if not messages:
        return ""

    last = messages[-1]

    # Pydantic model with .content
    if hasattr(last, "content"):
        return str(last.content or "")

    # Dict-like with "content"
    if isinstance(last, dict) and "content" in last:
        return str(last["content"] or "")

    # Fallback: stringify
    return str(last or "")
