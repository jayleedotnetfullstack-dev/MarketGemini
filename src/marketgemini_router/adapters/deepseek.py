# src/marketgemini_router/adapters/deepseek.py
import os
import time
import math
import requests


def _tok(s: str) -> int:
    return max(1, math.ceil(len(s) / 4))


def chat(cfg: dict, messages: list[dict], profile: str):
    """
    DeepSeek adapter (OpenAI-compatible /chat/completions).
    """
    t0 = time.time()

    api_key = os.getenv(cfg.get("api_key_env", ""), "")
    if not api_key:
        content = "[deepseek error] Missing DEEPSEEK_API_KEY"
        ti = _tok(" ".join(m.get("content", "") for m in messages))
        to = _tok(content)
        dur = int((time.time() - t0) * 1000)
        return content, ti, to, dur

    url = cfg["base_url"].rstrip("/") + "/chat/completions"

    prof = (cfg.get("profiles") or {}).get(
        profile,
        {"temperature": 0.2, "top_p": 1.0},
    )

    payload = {
        "model": cfg["model"],
        "messages": messages,
        "temperature": prof.get("temperature", 0.2),
        "top_p": prof.get("top_p", 1.0),
        "max_tokens": 800,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    r = requests.post(url, json=payload, headers=headers, timeout=60)
    dur = int((time.time() - t0) * 1000)
    ti = _tok(" ".join(m.get("content", "") for m in messages))

    if not r.ok:
        content = f"[deepseek error {r.status_code}] {r.text[:400]}"
        to = _tok(content)
        return content, ti, to, dur

    data = r.json()
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    content = msg.get("content") or choice.get("text")

    if not content:
        content = f"[deepseek response w/o content] {str(msg or choice)[:400]}"

    to = _tok(content)
    return content, ti, to, dur
