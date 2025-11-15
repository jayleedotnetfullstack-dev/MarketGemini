import os
import pytest
from fastapi.testclient import TestClient

from marketgemini_router.app import app

client = TestClient(app)


@pytest.mark.gemini_live
def test_router_v1_chat_with_auto_profile():
    """
    Live end-to-end test:

    /v1/chat  -> router -> cost-aware selection -> gemini adapter -> Gemini API
    """
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set; skipping live router test")

    payload = {
        "user_id": "jay",
        "session_id": "s1",
        "messages": [
            {
                "role": "user",
                "content": "Summarize gold price drivers in 3 bullets.",
            }
        ],
        "profile": "auto",  # router should pick 'summary'
    }

    resp = client.post("/v1/chat", json=payload)
    assert resp.status_code == 200

    data = resp.json()

    # sanity checks
    assert data["provider"] == "gemini"
    assert data["model"] == "gemini-2.5-flash"
    assert data["mode"] == "EXECUTE"
    assert isinstance(data["content"], str)
    assert len(data["content"]) > 0

    # profile should be auto-detected as 'summary'
    assert data["profile"] in ("summary", "factual")  # be a little forgiving

    # tokens & cost
    assert data["tokens_in"] > 0
    assert data["tokens_out"] > 0
    assert data["latency_ms"] >= 0
    assert data["cost_usd"] >= 0.0
