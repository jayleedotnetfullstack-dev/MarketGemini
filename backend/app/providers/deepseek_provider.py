import httpx
from typing import List, Tuple


class DeepseekProvider:
    def __init__(self, api_key: str, model: str, base_url="https://api.deepseek.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def invoke(self, messages: List[dict]) -> Tuple[str, int, int]:
        url = f"{self.base_url}/chat/completions"
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
            resp.raise_for_status()
            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return (
            content,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )
