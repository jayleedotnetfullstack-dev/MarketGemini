import os
import time
import math

import requests


def _tok(s: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, math.ceil(len(s) / 4))


def _post(url: str, payload: dict, api_key: str) -> requests.Response:
    """
    Try a few auth header styles compatible with Gemini:
      1) OpenAI-style Bearer
      2) x-goog-api-key
      3) ?key= query param
    """
    # 1) Bearer
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    if r.status_code in (401, 403):
        # 2) x-goog-api-key
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        r = requests.post(url, json=payload, headers=headers, timeout=60)
        if r.status_code in (401, 403):
            # 3) ?key=
            r = requests.post(
                f"{url}?key={api_key}",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=60,
            )
    return r


def chat(cfg: dict, messages: list[dict], profile: str):
    t0 = time.time()
    url = f"{cfg['base_url']}/chat/completions"

    # Read from env (.env is loaded in app.py via load_dotenv())
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        content = "[gemini error] Missing GEMINI_API_KEY. Check .env or environment."
        dur = int((time.time() - t0) * 1000)
        ti = _tok(" ".join(m.get("content", "") for m in messages))
        to = _tok(content)
        return content, ti, to, dur

    # Normalize model name in case it came as "models/gemini-2.5-flash"
    model = cfg.get("model", "")
    if model.startswith("models/"):
        model = model.split("/", 1)[1]

    prof = cfg.get("profiles", {}).get(profile, {"temperature": 0.2, "top_p": 1.0})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": prof.get("temperature", 0.2),
        "top_p": prof.get("top_p", 1.0),
        "max_tokens": 800,
    }

    r = _post(url, payload, api_key)
    dur = int((time.time() - t0) * 1000)
    ti = _tok(" ".join(m.get("content", "") for m in messages))

    # HTTP-level error → no crash, just return text
    if r.status_code >= 300:
        content = f"[gemini error {r.status_code}] {r.text[:400]}"
        to = _tok(content)
        return content, ti, to, dur

    # ---- Safe JSON parse ----
    try:
        data = r.json()
    except Exception as e:
        content = f"[gemini parse error] {e} :: {r.text[:400]}"
        to = _tok(content)
        return content, ti, to, dur

    # ---- Robust extraction of text content ----
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}

    content = None

    # 1) OpenAI-style: message.content is a string
    raw = msg.get("content")
    if isinstance(raw, str):
        content = raw

    # 2) OpenAI-style but content is list-of-parts
    if content is None and isinstance(raw, list):
        parts = []
        for part in raw:
            if isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
            else:
                parts.append(str(part))
        if parts:
            content = "".join(parts)

    # 3) Gemini-native: message.parts[] with { "text": "..." }
    if content is None and "parts" in msg:
        texts = []
        for part in msg["parts"]:
            if isinstance(part, dict) and "text" in part:
                texts.append(part["text"])
        if texts:
            content = "".join(texts)

    # 4) Fallback: some APIs use "text" directly on the choice
    if content is None:
        content = choice.get("text")

    # 5) Final fallback: dump message for debugging
    if not content:
        content = f"[gemini response w/o content] {str(msg or choice)[:400]}"

    to = _tok(content)
    return content, ti, to, dur
