import asyncio
import random
import os
import httpx

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_DEFAULT = os.getenv("GEMINI_MODEL_DEFAULT", "gemini-2.0-flash")


def extract_prompt(messages):
    if not messages:
        return ""
    last = messages[-1]
    if isinstance(last, dict):
        return last.get("content", "")
    if hasattr(last, "content"):
        return last.content
    return str(last)


async def call_gemini_api(messages, model_hint=None):
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set")

    prompt = extract_prompt(messages)
    model = model_hint or GEMINI_MODEL_DEFAULT

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}]
    }

    max_attempts = 5
    backoff = 1.0

    for attempt in range(max_attempts):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)

            if resp.status_code in (429, 503) and attempt < max_attempts - 1:
                await asyncio.sleep(backoff + random.random())
                backoff *= 2
                continue

            resp.raise_for_status()
            data = resp.json()

            candidates = data.get("candidates") or []
            parts = candidates[0].get("content", {}).get("parts") or []
            content = parts[0].get("text", "")

            usage = data.get("usageMetadata") or {}
            tokens_in = usage.get("promptTokenCount", 0)
            tokens_out = usage.get("candidatesTokenCount", 0)

            return content, tokens_in, tokens_out, model

        except Exception as ex:
            if (
                hasattr(ex, "response")
                and ex.response is not None
                and ex.response.status_code in (429, 503)
                and attempt < max_attempts - 1
            ):
                await asyncio.sleep(backoff + random.random())
                backoff *= 2
                continue
            raise

    raise RuntimeError("Gemini failed after retries")
