from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

import pytest
#@pytest.mark.skip(reason="temporarily disabling while refactoring")
def test_health(authed_client):
    res = authed_client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

def test_series_gold(authed_client):
    print("TEST authed_client headers:", dict(authed_client.headers))
    res = authed_client.get("/v1/series?asset=GOLD")
    print("DEBUG status:", res.status_code, "body:", res.text)   # visible with -s
    assert res.status_code == 200
    body = res.json()
    assert body["asset"] == "GOLD"
    assert "series" in body

def test_analyze_spike(authed_client):
    payload = {"values":[1,1,1,10,1,1]}
    res = authed_client.post("/v1/analyze", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert any(body["anomalies"])   # at least one True