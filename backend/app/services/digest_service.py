# backend/app/services/digest_service.py

from typing import List, Optional
import json
import re

from app.schemas import DigestRequest, DigestResponse
from app.providers.gemini_provider import call_gemini_api


def resolve_temperature(user_override: Optional[float]) -> float:
    """Fallback temperature logic (can adjust as needed)."""
    if user_override is not None:
        return float(user_override)
    return 0.5


async def run_digest(
    raw_prompt: str,
    messages: List,
    temperature: Optional[float] = None
) -> DigestResponse:
    """
    Compute intent, confidence, cleaned prompt, and suggestions.
    """

    # --- 1. Intent classification using LLM ---
    convo_lines = [f"{m.role}: {m.content}" for m in messages]
    convo_text = "\n".join(convo_lines)

    classifier_prompt = f"""
You are an intent classifier for a developer chat UI.

Read the conversation below and choose exactly ONE intent label from:
- bug_report
- explanation
- summary
- general

Return strictly JSON:
{{ "intent": "summary" }}

Conversation:
{convo_text}
"""

    intent = "general"
    temperature = resolve_temperature(temperature)

    try:
        content, *_ = await call_gemini_api(
            [{"role": "user", "content": classifier_prompt}],
            model_hint="gemini-2.5-flash",
            temperature=temperature,
        )

        text = content.strip()
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            data = json.loads(text[start:end + 1])
            candidate = str(data.get("intent", "")).lower()
            if candidate in {"bug_report", "explanation", "summary", "general"}:
                intent = candidate
    except Exception:
        pass  # fallback

    # --- 2. Confidence heuristic ---
    word_count = len(raw_prompt.split())
    has_time_range = bool(re.search(r"\b(year|month|day|last|since|\d{4})\b", raw_prompt.lower()))
    has_format = any(k in raw_prompt.lower() for k in ["bullet", "table", "chart", "list"])

    confidence = 0.0
    confidence += min(word_count / 20.0, 0.4)
    confidence += 0.3 if has_time_range else 0.0
    confidence += 0.3 if has_format else 0.0
    confidence = round(min(confidence, 1.0), 2)

    # --- 3. LLM-based confidence refinement ---
    llm_confidence: Optional[float] = None
    if confidence < 0.7:
        try:
            rating_prompt = (
                "Rate the clarity and specificity of the following user prompt "
                "on a scale from 0.0 to 1.0.\nReturn ONLY a number.\n\n"
                f"Prompt:\n{raw_prompt}"
            )

            content, *_ = await call_gemini_api(
                [{"role": "user", "content": rating_prompt}],
                model_hint="gemini-2.5-mini",
                temperature=0.0,
            )

            llm_confidence = float(
                re.findall(r"0?\.\d+|1\.0|0\.0|\b1\b|\b0\b", content)[0]
            )
            confidence = round((confidence * 0.6) + (llm_confidence * 0.4), 2)

        except Exception:
            pass

    # --- 4. Prompt optimization / guidance ---
    suggestions: List[str] = []

    # Start with raw_prompt
    cleaned_prompt = raw_prompt

    if confidence < 0.4:
        suggestions.append(
            "Your prompt may be too broad. Try adding a time range, format, or comparison."
        )

        # Adaptive example generation
        try:
            rewrite_prompt = (
                "Rewrite the following user prompt to be more specific and actionable. "
                "If missing, add a time range and an output format (bullets, table, etc). "
                "Return ONLY the improved prompt.\n\n"
                f"User prompt:\n{raw_prompt}"
            )

            content, *_ = await call_gemini_api(
                [{"role": "user", "content": rewrite_prompt}],
                model_hint="gemini-2.5-mini",
                temperature=0.3,
            )

            improved = content.strip()
            if improved and len(improved) > 10:
                suggestions.append(f"Example improved prompt: {improved}")

        except Exception:
            pass

    # --- Light prompt normalization for medium/high confidence ---
    else:
        # 1️⃣ Lowercase
        cleaned_prompt = raw_prompt.lower()

        # 2️⃣ Remove common stopwords
        cleaned_prompt = re.sub(
            r"\b(the|is|are|please|could you|would you|kindly)\b",
            "",
            cleaned_prompt,
            flags=re.I,
        )

        # 3️⃣ Remove duplicate consecutive words
        cleaned_prompt = re.sub(r"\b(\w+)( \1\b)+", r"\1", cleaned_prompt, flags=re.I)

        # 4️⃣ Remove extra whitespace
        cleaned_prompt = re.sub(r"\s+", " ", cleaned_prompt).strip()

        # 5️⃣ Remove trailing punctuation
        cleaned_prompt = re.sub(r"[.?!]+$", "", cleaned_prompt)

        # 6️⃣ Capitalize first letter
        if cleaned_prompt:
            cleaned_prompt = cleaned_prompt[0].upper() + cleaned_prompt[1:]

    # --- 5. Profile mapping ---
    # Map internal intents to valid profile IDs
    if intent in {"summary", "explanation"}:
        profile = "summary"  # map "explanation" to "summary"
    else:
        profile = "general"

    # Decide response type
    if confidence >= 0.8:
        response_type = "optimized"
    elif confidence >= 0.4:
        response_type = "neutral"
    else:
        response_type = "user_guidance"

    # Quick debug
    print("DEBUG: confidence=", confidence)
    print("DEBUG: cleaned_prompt=", cleaned_prompt)
    print("DEBUG: suggestions=", suggestions)

    return DigestResponse(
        intent=intent,
        profile=profile,
        confidence=confidence,
        type=response_type,
        cleaned_prompt=cleaned_prompt,
        suggested_prompt=None,
        suggestions=suggestions,
    )
