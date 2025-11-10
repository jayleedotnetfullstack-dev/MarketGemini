import pytest

def test_anomaly_get_for_asset(authed_client):
    r = authed_client.get("/v1/anomaly", params={"asset": "GOLD", "window": 10, "threshold": 2.5})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window"] == 10
    assert body["threshold"] == 2.5
    assert len(body["scores"]) == len(body["flags"])
    assert any(body["flags"])  # expect at least one spike in sample data

def test_anomaly_post_payload(authed_client):
    payload = {"values": [1,1,1,10,1,1], "window": 3, "threshold": 2.0}
    r = authed_client.post("/v1/anomaly", json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["window"] == 3
    assert body["threshold"] == 2.0
    assert len(body["scores"]) == len(payload["values"])
    assert any(body["flags"])
