import httpx
from typing import List, Tuple


class DeepseekProvider:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.deepseek.com/v1",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _normalize_messages(self, messages: List[dict]) -> List[dict]:
        """
        DeepSeek is STRICT:
        - role must be system|user|assistant
        - content must be a STRING
        - no extra keys
        """
        normalized = []

        for m in messages:
            role = m.get("role", "user")

            if role not in ("system", "user", "assistant"):
                role = "user"

            content = m.get("content", "")

            if isinstance(content, dict):
                content = content.get("text") or str(content)
            else:
                content = str(content)

            if content.strip():
                normalized.append(
                    {
                        "role": role,
                        "content": content.strip(),
                    }
                )

        if not normalized:
            normalized = [{"role": "user", "content": "Hello"}]

        return normalized

    async def invoke(
        self,
        messages: List[dict],
        temperature: float = 0.4,  # ✅ added
    ) -> Tuple[str, int, int]:

        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": self._normalize_messages(messages),
            "temperature": temperature,  # ✅ added
        }

        print("DEEPSEEK REQUEST PAYLOAD:", payload)

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)

            # ✅ SHOW REAL ERROR BODY INSTEAD OF GENERIC 400
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"DeepSeek {resp.status_code}: {resp.text}"
                )

            data = resp.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}) or {}

        return (
            content,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
        )
