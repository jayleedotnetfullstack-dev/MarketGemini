import json
from unittest.mock import patch, Mock

from marketgemini_router.adapters import gemini


def test_gemini_adapter_parses_choices_parts():
    cfg = {
        "base_url": "https://fake",
        "model": "gemini-2.5-flash",
        "api_key_env": "GEMINI_API_KEY",
        "profiles": {"summary": {"temperature": 0.2, "top_p": 1.0}},
    }

    messages = [{"role": "user", "content": "test"}]

    fake_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "Hello from mock Gemini."}
                    ],
                }
            }
        ]
    }

    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.ok = True
    mock_resp.json.return_value = fake_response
    mock_resp.text = json.dumps(fake_response)

    with patch("marketgemini_router.adapters.gemini._post", return_value=mock_resp):
        content, ti, to, dur = gemini.chat(cfg, messages, profile="summary")

    assert "hello from mock gemini" in content.lower()
    assert ti > 0
    assert to > 0
