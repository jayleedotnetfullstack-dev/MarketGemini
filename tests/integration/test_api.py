# marketgemini/backend/tests/test_api.py
import pytest

def test_health(authed_client):
    res = authed_client.get("/healthz")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}

def test_series_gold(authed_client):
    # use params dict so FastAPI sees proper query args
    res = authed_client.get("/v1/series", params={"asset": "GOLD"})
    if res.status_code != 200:
        print("DEBUG /v1/series:", res.status_code, res.text)
    assert res.status_code == 200
    body = res.json()
    assert body["asset"] == "GOLD"
    assert "series" in body
    assert isinstance(body["series"], list)
    assert len(body["series"]) > 0

def test_analyze_spike(authed_client):
    payload = {
        "values": [1, 1, 1, 10, 1, 1],
        # window and threshold have defaults, but being explicit avoids 422s if schema changes
        "window": 30,
        "threshold": 3.5,
    }
    res = authed_client.post("/v1/analyze", json=payload)
    if res.status_code != 200:
        print("DEBUG /v1/analyze:", res.status_code, res.text)
    assert res.status_code == 200
    body = res.json()
    assert "anomalies" in body
    assert any(body["anomalies"])  # expect at least one spike
