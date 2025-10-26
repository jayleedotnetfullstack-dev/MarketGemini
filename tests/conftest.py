# tests/conftest.py
from __future__ import annotations

import os
import json
import base64
from pathlib import Path
from typing import List, Tuple
import pytest
from fastapi.testclient import TestClient

# ---------- Paths & .env ----------
ROOT = Path(__file__).resolve().parents[1]  # repo root
# Optional: load .env from repo root for local runs (CI may inject env separately)
try:
    from dotenv import load_dotenv  # type: ignore
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
except Exception:
    pass

# 👇 NEW: print out key envs immediately after loading .env
print(
    "[pytest startup] "
    f"AUTH_MODE={os.getenv('AUTH_MODE')}, "
    f"ENABLE_GOOGLE_TESTS={os.getenv('ENABLE_GOOGLE_TESTS')}, "
    f"TEST_MODE={os.getenv('TEST_MODE')}"
)

# With src/ layout and `pip install -e .`, we can import the app package directly:
from marketgemini_backend.app.main import app  # noqa: E402

# ---------- Auth env ----------
AUTH_MODE = (os.getenv("AUTH_MODE", "HS256") or "").strip().upper()

# Google OIDC env (used only when AUTH_MODE is OIDC/OIDC_DIRECT)
GOOGLE_AUDIENCE   = (os.getenv("GOOGLE_AUDIENCE") or os.getenv("GOOGLE_CLIENT_ID") or "").strip()
GOOGLE_TEST_IDTOK = os.getenv("GOOGLE_TEST_ID_TOKEN")
GOOGLE_ISS        = (os.getenv("GOOGLE_ISS") or "").strip()
GOOGLE_JWKS_URI   = (os.getenv("GOOGLE_JWKS_URI") or "").strip()

# Opt-in switch for OIDC tests
ENABLE_GOOGLE_TESTS = (os.getenv("ENABLE_GOOGLE_TESTS", "")).lower() in ("1", "true", "yes", "on")

def _mask(tok: str | None, keep: int = 12) -> str:
    if not tok:
        return "<none>"
    return tok[:keep] + "...(masked)..."

def _jwt_payload_unsafe(tok: str) -> dict:
    """Inspect payload without verifying signature (diagnostics only)."""
    try:
        parts = tok.split(".")
        if len(parts) < 2:
            return {}
        p = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(p.encode("ascii")))
    except Exception:
        return {}

def _has_google_env() -> bool:
    return all([
        GOOGLE_AUDIENCE,
        GOOGLE_TEST_IDTOK,
        GOOGLE_ISS,
        GOOGLE_JWKS_URI,
    ])

# ---------- Pytest controls ----------
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--enable-google-tests",
        action="store_true",
        default=False,
        help="Run tests marked with @pytest.mark.google (otherwise auto-skip).",
    )

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "google: tests that require Google ID tokens")
    # 👇 NEW: print a concise env summary at config time
    print("\n=== Environment Summary ===")
    print(f"AUTH_MODE={os.getenv('AUTH_MODE')}")
    print(f"ENABLE_GOOGLE_TESTS={os.getenv('ENABLE_GOOGLE_TESTS')}")
    print(f"TEST_MODE={os.getenv('TEST_MODE')}")
    print(f"AUTH_TRACE={os.getenv('AUTH_TRACE')}")
    print(f"LOG_LEVEL={os.getenv('LOG_LEVEL')}")
    print(f"TEST_MODE_ENFORCE_EXP={os.getenv('TEST_MODE_ENFORCE_EXP')}")
    print("===========================\n")

def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]) -> None:
    """Gate @google tests unless explicitly enabled."""
    if AUTH_MODE == "HS256":
        # In HS256 mode, we don’t auto-skip; tests can still run using HS256 dev token.
        return

    enable_flag = config.getoption("--enable-google-tests")
    if enable_flag or ENABLE_GOOGLE_TESTS:
        return

    skip_google = pytest.mark.skip(
        reason=("Skipping @google tests. Enable with --enable-google-tests or set "
                "ENABLE_GOOGLE_TESTS=true. Requires GOOGLE_ISS, GOOGLE_JWKS_URI, "
                "GOOGLE_AUDIENCE/GOOGLE_CLIENT_ID, GOOGLE_TEST_ID_TOKEN.")
    )
    for item in items:
        if "google" in item.keywords:
            item.add_marker(skip_google)

# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def base_client() -> TestClient:
    return TestClient(app)

@pytest.fixture
def authed_client(request: pytest.FixtureRequest, base_client: TestClient) -> TestClient:
    """
    Adaptive auth client:
      - HS256: issue internal dev token with scopes
      - OIDC / OIDC_DIRECT: exchange GOOGLE_TEST_ID_TOKEN -> internal HS256 access token
    """
    if AUTH_MODE == "HS256":
        # internal dev token from auth.internal
        from marketgemini_backend.app.auth.internal import make_dev_token
        tok = make_dev_token(scope="series:read analyze:run")
        c = TestClient(app)
        c.headers.update({"Authorization": f"Bearer {tok}"})
        payload = _jwt_payload_unsafe(tok)
        print(f"[authed_client] HS256 token={_mask(tok)} scope={payload.get('scope')!r}")
        return c

    # --- OIDC branches ---
    enable_flag = request.config.getoption("--enable-google-tests")
    if not (enable_flag or ENABLE_GOOGLE_TESTS):
        pytest.skip("OIDC tests disabled: use --enable-google-tests or set ENABLE_GOOGLE_TESTS=true")
    if not _has_google_env():
        pytest.skip("Missing OIDC env: GOOGLE_ISS, GOOGLE_JWKS_URI, GOOGLE_AUDIENCE/CLIENT_ID, GOOGLE_TEST_ID_TOKEN")

    # Exchange id_token -> internal access token (should include required scopes)
    r = base_client.post("/auth/google/exchange", json={"id_token": GOOGLE_TEST_IDTOK})
    print(f"[authed_client] exchange status={r.status_code} body={r.text[:240]}")
    assert r.status_code == 200, f"/auth/google/exchange failed: {r.status_code} {r.text}"

    body = r.json()
    access = body.get("access_token")
    assert access, "Exchange response missing 'access_token'"

    payload = _jwt_payload_unsafe(access)
    scope_str = payload.get("scope") or ""
    need = {"series:read", "analyze:run"}
    missing = need - set(scope_str.split())
    assert not missing, f"Access token missing scopes: {missing}"

    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {access}"})
    return c

@pytest.fixture(scope="session")
def google_tokens(base_client: TestClient) -> Tuple[str, str | None]:
    if AUTH_MODE == "HS256":
        pytest.skip("google_tokens fixture only for OIDC modes")
    if not _has_google_env():
        pytest.skip("Missing OIDC env variables")

    r = base_client.post("/auth/google/exchange", json={"id_token": GOOGLE_TEST_IDTOK})
    assert r.status_code == 200, f"/auth/google/exchange failed: {r.status_code} {r.text}"
    body = r.json()
    access = body.get("access_token")
    refresh = body.get("refresh_token")
    print(f"[google_tokens] access={_mask(access)}, refresh={_mask(refresh)}")
    return access or "", refresh

@pytest.fixture
def google_authed_client(authed_client: TestClient) -> TestClient:
    """Alias so tests that expect 'google_authed_client' still work in HS256 mode."""
    return authed_client
