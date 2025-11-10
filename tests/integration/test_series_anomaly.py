import pytest

@pytest.mark.google
def test_series_with_anomaly(authed_client):
    resp = authed_client.get(
        "/v1/series",
        params={
            "asset": "GOLD",
            "anomaly": "true",
            "anomaly_window": 10,
            "anomaly_threshold": 2.5,
        },
    )

    assert resp.status_code == 200
    data = resp.json()

    assert data["asset"] == "GOLD"
    assert "series" in data and len(data["series"]) > 0

    assert "anomalies" in data
    an = data["anomalies"]

    assert an["window"] == 10
    assert an["threshold"] == 2.5
    assert len(an["scores"]) == len(data["series"])
    assert len(an["flags"]) == len(data["series"])
    assert any(an["flags"])  # gold should have some spikes
