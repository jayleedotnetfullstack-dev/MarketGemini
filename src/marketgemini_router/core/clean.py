# src/marketgemini_router/core/clean.py

from __future__ import annotations
from typing import List, Dict


def _normalize_whitespace(text: str) -> str:
    """
    Simple whitespace normalization:
      - strip leading/trailing spaces
      - collapse internal runs of whitespace to a single space
    """
    return " ".join(text.split())


def clean_prompt(messages: List[Dict]) -> List[Dict]:
    """
    Clean/normalize messages before sending to provider.

    - Ensures each message has 'role' and 'content'
    - Normalizes whitespace in content
    - (Hook point for future spam/noise filters or truncation)
    """
    cleaned: List[Dict] = []

    for m in messages:
        role = m.get("role") or "user"
        content = m.get("content", "")

        # normalize whitespace
        content = _normalize_whitespace(content)

        # You can add more rules here later (e.g. strip debugging noise, logs, etc.)
        cleaned.append(
            {
                "role": role,
                "content": content,
            }
        )

    return cleaned
