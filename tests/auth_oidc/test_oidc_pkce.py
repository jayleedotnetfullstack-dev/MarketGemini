"""PKCE flow tests: mocked Google discovery + token exchange (no real Google)."""

import json
import base64
import time
import urllib.parse as urlparse
from typing import Dict

import pytest
from fastapi.testclient import TestClient
import importlib

# Mark: gated by --enable-google-tests or ENABLE_GOOGLE_TESTS=true
pytestmark = pytest.mark.google

# ---- Constants for the mocked environment ----
CLIENT_ID = "dummy-client.apps.googleusercontent.com"
REDIRECT_URI = "http://localhost:8000/auth/callback"
DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def _jwt(id_claims: Dict) -> str:
    """Return a minimal mock JWT (header.payload.signature). Signature is not verified in TEST_MODE."""
    def b64(o: Dict) -> str:
        raw = json.dumps(o, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    header = b64({"alg": "RS256", "kid": "mock"})
    payload = b64(id_claims)
    sig = "signature"
    return f"{header}.{payload}.{sig}"


@pytest.fixture(autouse=True)
def _env_setup(monkeypatch):
    """Set env BEFORE module reload so google router will use test values."""
    monkeypatch.setenv("AUTH_MODE", "OIDC")
    monkeypatch.setenv("ENABLE_GOOGLE_TESTS", "true")
    monkeypatch.setenv("TEST_MODE", "true")  # skip signature verification in tests
    monkeypatch.setenv("GOOGLE_DISCOVERY", DISCOVERY_URL)
    monkeypatch.setenv("GOOGLE_AUDIENCE", CLIENT_ID)
    monkeypatch.setenv("GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "dummy-secret")
    monkeypatch.setenv("OIDC_REDIRECT_URI", REDIRECT_URI)
    monkeypatch.setenv("BASE_URL", "http://localhost:8000")


@pytest.fixture
def app_instance():
    """
    Reload modules so that:
      1) app.auth_google re-reads env constants (CLIENT_ID, DISCOVERY, etc.)
      2) app.main rebuilds FastAPI app and re-includes the refreshed router
    """
    import marketgemini_backend.app.auth.google as auth_google
    import marketgemini_backend.app.main as main
    importlib.reload(auth_google)
    importlib.reload(main)
    return main.app


def test_pkce_login_redirect_contains_required_params(httpx_mock, app_instance):
    """GET /auth/login should 302 to Google with proper PKCE params and client_id from test env."""
    # Mock discovery
    httpx_mock.add_response(
        url=DISCOVERY_URL,
        json={"authorization_endpoint": AUTH_URL, "token_endpoint": TOKEN_URL},
    )

    c = TestClient(app_instance, follow_redirects=False)
    r = c.get("/auth/login")
    assert r.status_code in (302, 307)
    loc = r.headers["Location"]

    parsed = urlparse.urlparse(loc)
    qs = dict(urlparse.parse_qsl(parsed.query))

    assert parsed.scheme in ("https", "http")
    assert parsed.netloc
    assert qs["client_id"] == CLIENT_ID
    assert qs["redirect_uri"] == REDIRECT_URI
    assert qs["response_type"] == "code"
    assert "openid" in qs["scope"]
    assert "email" in qs["scope"]
    assert "profile" in qs["scope"]
    assert qs["code_challenge_method"] == "S256"
    assert qs.get("code_challenge")
    assert qs.get("state")  # CSRF protection


def test_pkce_callback_happy_path_exchanges_code_for_internal_token(httpx_mock, app_instance):
    # Discovery is called twice: once in /auth/login and once in /auth/callback.
    disc_payload = {"authorization_endpoint": AUTH_URL, "token_endpoint": TOKEN_URL}
    httpx_mock.add_response(url=DISCOVERY_URL, json=disc_payload)  # for /auth/login
    httpx_mock.add_response(url=DISCOVERY_URL, json=disc_payload)  # for /auth/callback

    # Token endpoint mock (consumed during /auth/callback)
    now = int(time.time())
    id_token = _jwt({
        "iss": "https://accounts.google.com",
        "aud": CLIENT_ID,
        "sub": "1234567890",
        "email": "tester@example.com",
        "email_verified": True,
        "iat": now, "exp": now + 3600,
    })
    httpx_mock.add_response(
        url=TOKEN_URL,
        method="POST",
        json={
            "access_token": "ya29.mock",
            "id_token": id_token,
            "token_type": "Bearer",
            "expires_in": 3600,
        },
    )

    c = TestClient(app_instance, follow_redirects=False)

    # 1) Start login (sets cookie & returns redirect with state)
    start = c.get("/auth/login")
    assert start.status_code in (302, 307)
    loc = start.headers["Location"]
    qs = dict(urlparse.parse_qsl(urlparse.urlparse(loc).query))
    state = qs["state"]

    # 2) Callback with SAME state triggers token POST and returns internal token
    cb = c.get(f"/auth/callback?code=mock_code&state={state}")
    assert cb.status_code == 200, cb.text
    body = cb.json()

    access = body["access_token"]
    assert body["token_type"] == "Bearer"
    assert isinstance(access, str) and access.count(".") == 2

    # 3) Protected endpoint with internal token
    r = c.get("/v1/series", params={"asset": "GOLD"}, headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["asset"] == "GOLD"
    assert len(j["series"]) > 0

def test_pkce_callback_rejects_bad_state(httpx_mock, app_instance):
    """If state/CSRF check fails, callback should 400/401/403."""
    httpx_mock.add_response(
        url=DISCOVERY_URL,
        json={"authorization_endpoint": AUTH_URL, "token_endpoint": TOKEN_URL},
    )
    c = TestClient(app_instance, follow_redirects=False)
    _ = c.get("/auth/login")
    bad = c.get("/auth/callback?code=x&state=WRONG")
    assert bad.status_code in (400, 401, 403)
