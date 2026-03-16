# backend/app/providers/deepseek_provider.py
from typing import List, Tuple, Optional

import httpx
from fastapi import HTTPException

from app.schemas.core import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL


class DeepseekProvider:
    """
    Thin wrapper around DeepSeek's chat completion API.

    Usage pattern (from call_service or similar):

        provider = DeepseekProvider(model="deepseek-chat")
        content, in_tokens, out_tokens = await provider.invoke(messages)

    where `messages` is a list of dicts:
        [{"role": "user", "content": "hello"}, ...]
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> None:
        # Prefer explicit arguments, fall back to env-configured defaults
        self.api_key = (api_key or DEEPSEEK_API_KEY or "").strip()
        self.model = model
        self.base_url = (base_url or DEEPSEEK_BASE_URL or "").strip()

        if not self.api_key:
            # Fail fast if not configured; upstream can catch HTTPException
            raise HTTPException(
                status_code=500,
                detail="DeepSeek not configured: DEEPSEEK_API_KEY is missing",
            )
        if not self.base_url:
            raise HTTPException(
                status_code=500,
                detail="DeepSeek not configured: DEEPSEEK_BASE_URL is missing",
            )

    async def invoke(self, messages: List[dict]) -> Tuple[str, int, int]:
        """
        Invoke DeepSeek chat completion.

        :param messages: OpenAI-style list of messages:
                         [{"role": "user", "content": "..."}, ...]
        :return: (content, input_tokens, output_tokens)
        """
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

        # Raise a clean HTTPException for non-200 responses so the router can surface it
        if resp.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"DeepSeek error {resp.status_code}: {resp.text}",
            )

        data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}) or {}
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        return content, input_tokens, output_tokens
