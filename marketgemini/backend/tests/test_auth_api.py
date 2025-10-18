# marketgemini/backend/tests/test_auth_api.py
import os
import pytest

# Make this module selectable with:  pytest -m google
pytestmark = pytest.mark.google

AUTH_MODE = (os.getenv("AUTH_MODE", "HS256") or "").strip().upper()

# Use the shared TestClient fixtures from conftest.py:
#   - base_client: unauthenticated client
#   - authed_client: HS256 token client (HS256 mode) or OIDC token client (OIDC when enabled)

def test_protected_requires_token(base_client):
    r = base_client.get("/v1/series", params={"asset": "GOLD"})
    assert r.status_code == 401


def test_series_with_valid_token(authed_client):
    r = authed_client.get("/v1/series", params={"asset": "GOLD"})
    assert r.status_code == 200
    body = r.json()
    assert body["asset"] == "GOLD"
    assert len(body["series"]) > 0


def test_analyze_with_scope_enforced(base_client):
    """
    This test needs two tokens with different scopes to check 403 vs 200.
    That's easy in HS256 (we can mint tokens); in OIDC it's provider-dependent.
    So:
      - HS256: run the scope assertions using make_dev_token
      - OIDC : skip (or adapt if your exchanged token carries adjustable scopes)
    """
    if AUTH_MODE != "HS256":
        pytest.skip("Scope-variation test is HS256-only (cannot mint custom-scope OIDC tokens here).")

    # HS256 path: mint tokens with specific scopes
    from app.auth import make_dev_token

    # Missing analyze:run -> expect 403
    tok_no_analyze = make_dev_token(scope="series:read")
    r = base_client.post(
        "/v1/analyze",
        json={"values": [1, 1, 1, 10, 1, 1]},
        headers={"Authorization": f"Bearer {tok_no_analyze}"},
    )
    assert r.status_code == 403

    # With analyze:run -> expect 200
    tok_analyze = make_dev_token(scope="analyze:run")
    r2 = base_client.post(
        "/v1/analyze",
        json={"values": [1, 1, 1, 10, 1, 1]},
        headers={"Authorization": f"Bearer {tok_analyze}"},
    )
    assert r2.status_code == 200
    assert any(r2.json()["anomalies"])

