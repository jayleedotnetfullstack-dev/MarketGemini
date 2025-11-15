import os
import pytest

from marketgemini_router.core.config import CFG
from marketgemini_router.adapters import gemini


@pytest.mark.gemini_live
def test_gemini_adapter_chat_smoke():
    """
    Live smoke test against Gemini adapter.

    Requires GEMINI_API_KEY in env (or .env loaded by app).
    """
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set; skipping live Gemini test")

    # Base provider config from router.yml
    base_cfg = CFG["providers"]["gemini"]

    # Attach the summary profile so adapter has temperature/top_p
    cfg = dict(base_cfg)
    cfg["profiles"] = {
        "summary": CFG["profiles"]["summary"],
    }

    messages = [
        {"role": "user", "content": "Say 'OK' in one short sentence."}
    ]

    content, tokens_in, tokens_out, latency_ms = gemini.chat(
        cfg,
        messages,
        profile="summary",
    )

    # Basic assertions
    assert isinstance(content, str)
    assert "ok" in content.lower()
    assert tokens_in > 0
    assert tokens_out > 0
    assert latency_ms >= 0
