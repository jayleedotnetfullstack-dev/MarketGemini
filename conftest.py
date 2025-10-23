# ProjectAI/conftest.py
from __future__ import annotations

import os
import sys
import json
import base64
from pathlib import Path
from typing import List, Tuple
import pytest
from fastapi.testclient import TestClient

# ============ Paths & .env ============
ROOT = Path(__file__).resolve().parent

# Best-effort .env load (repo-root .env)
try:
    from dotenv import load_dotenv  # type: ignore
    env_path = ROOT / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
except Exception:
    pass

# Ensure backend imports
BACKEND_DIR = ROOT / "marketgemini" / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

# ============ Auth env ============
AUTH_MODE = (os.getenv("AUTH_MODE", "HS256") or "").strip().upper()

# Google (OIDC)
GOOGLE_AUD       = (os.getenv("GOOGLE_AUDIENCE") or "").strip()
GOOGLE_TEST_ID_TOKEN = os.getenv("GOOGLE_TEST_ID_TOKEN")
GOOGLE_ISS       = (os.getenv("GOOGLE_ISS") or "").strip()
GOOGLE_JWKS_URI  = (os.getenv("GOOGLE_JWKS_URI") or "").strip()

# test gating
ENABLE_GOOGLE_TESTS = (os.getenv("ENABLE_GOOGLE_TESTS", "")).lower() in ("1", "true", "yes", "on")

def _mask(tok: str | None, keep: int = 12) -> str:
    if not tok:
        return "<none>"
    return tok[:keep] + "...(masked)..."

def _jwt_payload_unsafe(tok: str) -> dict:
    """
    Inspect payload without verifying signature (for diagnostics only).
    """
    try:
        parts = tok.split(".")
        if len(parts) < 2:
            return {}
        p = parts[1]
        # pad base64
        p += "=" * ((4 - len(p) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(p.encode("ascii")))
    except Exception:
        return {}

def _has_google_env() -> bool:
    # Keep the check consistent with skip messaging
    return (
        AUTH_MODE == "OIDC"
        and bool(GOOGLE_AUD)
        and bool(GOOGLE_TEST_ID_TOKEN)
        and bool(GOOGLE_ISS)
        and bool(GOOGLE_JWKS_URI)
    )

# ============ Pytest controls ============
def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--enable-google-tests",
        action="store_true",
        default=False,
        help="Run tests marked with @pytest.mark.google "
             "(otherwise auto-skip in OIDC unless ENABLE_GOOGLE_TESTS=true).",
    )

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "google: tests that require Google ID tokens (skipped by default)")

def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]) -> None:
    """
    In OIDC mode: keep the opt-in gate for @google tests.
    In HS256 mode: do NOT skip @google tests (run them with HS256 client instead).
    """
    if AUTH_MODE == "HS256":
        return

    enable_flag = config.getoption("--enable-google-tests")
    if enable_flag or ENABLE_GOOGLE_TESTS:
        return

    skip_google = pytest.mark.skip(
        reason=("Skipping @google tests. Enable with --enable-google-tests or set "
                "ENABLE_GOOGLE_TESTS=true. (Requires AUTH_MODE=OIDC, GOOGLE_ISS, GOOGLE_JWKS_URI, "
                "GOOGLE_AUDIENCE, GOOGLE_TEST_ID_TOKEN.)")
    )
    for item in items:
        if "google" in item.keywords:
            item.add_marker(skip_google)

# ============ Fixtures ============
@pytest.fixture(scope="session")
def base_client() -> TestClient:
    return TestClient(app)

@pytest.fixture
def authed_client(request: pytest.FixtureRequest, base_client: TestClient) -> TestClient:
    """
    Adaptive auth client:
      - HS256: returns HS256 dev-token client (scopes: series:read analyze:run)
      - OIDC : exchanges GOOGLE_TEST_ID_TOKEN -> internal HS256 access token (must include same scopes)
    """
    if AUTH_MODE == "HS256":
        from app.auth import make_dev_token
        tok = make_dev_token(scope="series:read analyze:run")
        c = TestClient(app)
        c.headers.update({"Authorization": f"Bearer {tok}"})
        print(f"[authed_client] mode=HS256 token={_mask(tok)}")
        # diag: show scopes
        payload = _jwt_payload_unsafe(tok)
        print(f"[authed_client] HS256 payload scope={payload.get('scope')!r}")
        return c

    # --- OIDC branch ---
    enable_flag = request.config.getoption("--enable-google-tests")
    if not (enable_flag or ENABLE_GOOGLE_TESTS):
        pytest.skip("OIDC tests disabled: use --enable-google-tests or set ENABLE_GOOGLE_TESTS=true")

    if not _has_google_env():
        pytest.skip("Missing OIDC env (AUTH_MODE=OIDC, GOOGLE_ISS, GOOGLE_JWKS_URI, GOOGLE_AUDIENCE, GOOGLE_TEST_ID_TOKEN).")

    # Exchange id_token -> internal access token (must carry series:read analyze:run)
    r = base_client.post("/auth/google/exchange", json={"id_token": GOOGLE_TEST_ID_TOKEN})
    print(f"[authed_client] exchange status={r.status_code} body={r.text[:240]}")
    assert r.status_code == 200, f"/auth/google/exchange failed: {r.status_code} {r.text}"

    body = r.json()
    access = body.get("access_token")
    assert access, "Exchange response missing 'access_token'"

    # diag: check scopes inside the returned internal token
    payload = _jwt_payload_unsafe(access)
    scope_str = payload.get("scope") or ""
    print(f"[authed_client] OIDC access={_mask(access)} scope={scope_str!r}")

    # Ensure we have both scopes needed by tests
    need = {"series:read", "analyze:run"}
    have = set(scope_str.split())
    missing = need - have
    # Fail fast so tests don't 401/403 later with less helpful messages
    assert not missing, f"Exchanged access token missing scopes: {missing}. " \
                        f"Update /auth/google/exchange to mint internal token with 'series:read analyze:run'."

    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {access}"})
    return c

@pytest.fixture(scope="session")
def google_tokens(base_client: TestClient) -> Tuple[str, str | None]:
    if not _has_google_env():
        pytest.skip("Missing OIDC env (AUTH_MODE=OIDC, GOOGLE_ISS, GOOGLE_JWKS_URI, GOOGLE_AUDIENCE, GOOGLE_TEST_ID_TOKEN).")

    r = base_client.post("/auth/google/exchange", json={"id_token": GOOGLE_TEST_ID_TOKEN})
    assert r.status_code == 200, f"/auth/google/exchange failed: {r.status_code} {r.text}"
    body = r.json()
    access = body.get("access_token")
    refresh = body.get("refresh_token")
    print(f"[google_tokens] access={_mask(access)}, refresh={_mask(refresh)}")
    return access or "", refresh

@pytest.fixture
def google_authed_client(authed_client: TestClient) -> TestClient:
    """
    Wrapper so tests using google_authed_client still run in HS256 mode.
    In HS256, this returns the HS256 authed client.
    In OIDC, it returns the OIDC authed client (same as authed_client above).
    """
    return authed_client
