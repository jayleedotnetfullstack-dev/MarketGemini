# backend/app/services/digest_service.py

from typing import List

from app.schemas import DigestRequest, DigestResponse
from app.routing.prompt_helpers import extract_prompt


async def run_digest(req: DigestRequest) -> DigestResponse:
    """
    Heuristic digest:
    - Computes confidence based on prompt length / richness
    - Returns suggestions when the prompt is too short or too long
    """

    # Reuse the same prompt extraction logic as router
    raw = extract_prompt(req.messages)
    text = (raw or "").strip()
    words: List[str] = text.split()
    word_count = len(words)
    char_len = len(text)

    intent = "general_question"
    profile = "summary"
    confidence = 0.85
    suggestions: List[str] = []

    # Very vague: "why?", "help", "?", etc.
    if char_len < 5 or word_count <= 1:
        intent = "too_vague"
        confidence = 0.20
        suggestions.append(
            "Your prompt is too short. Please add what topic or situation you're asking about."
        )
        suggestions.append(
            "Example: instead of 'why?', try 'Why did gold prices rise in 2024?'"
        )

    # Short / low-context: "why gold?", "explain inflation"
    elif word_count < 5:
        intent = "vague"
        confidence = 0.45
        suggestions.append(
            "Try adding a bit more context (who/what/when) so the answer can be more precise."
        )
        suggestions.append(
            "Example: 'Explain how inflation affects long-term mortgage rates in the US.'"
        )

    # Very long / rambling
    elif word_count > 40:
        intent = "long_question"
        confidence = 0.70
        suggestions.append(
            "Your question is quite long. Consider summarizing the key points to get a sharper answer."
        )

    # Normal, well-sized question
    else:
        intent = "well_formed"
        confidence = 0.90

    return DigestResponse(
        intent=intent,
        profile=profile,
        confidence=confidence,
        cleaned_prompt=text or raw,
        suggestions=suggestions,
    )
