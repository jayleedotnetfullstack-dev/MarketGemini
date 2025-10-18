# ProjectAI/conftest.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import List, Tuple
import pytest
from fastapi.testclient import TestClient

# ============ Paths & .env ============
ROOT = Path(__file__).resolve().parent

# Best-effort .env load
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
GOOGLE_AUD = (os.getenv("GOOGLE_AUDIENCE") or "").strip()
GOOGLE_TEST_ID_TOKEN = os.getenv("GOOGLE_TEST_ID_TOKEN")

def _mask(tok: str | None, keep: int = 12) -> str:
    if not tok:
        return "<none>"
    return tok[:keep] + "...(masked)..."

def _has_google_env() -> bool:
    return AUTH_MODE == "OIDC" and bool(GOOGLE_AUD) and bool(GOOGLE_TEST_ID_TOKEN)

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
    config.addinivalue_line("markers", "google: tests that require live Google ID tokens (skipped by default)")

def pytest_collection_modifyitems(config: pytest.Config, items: List[pytest.Item]) -> None:
    """
    In OIDC mode: keep the opt-in gate for @google tests.
    In HS256 mode: do NOT skip @google tests (run them with HS256 client instead).
    """
    # If HS256, let all tests (including google-marked) run.
    if AUTH_MODE == "HS256":
        return

    # Only gate when OIDC mode is selected.
    enable_flag = config.getoption("--enable-google-tests")
    enable_env = os.getenv("ENABLE_GOOGLE_TESTS", "").lower() in ("1", "true", "yes", "on")
    if enable_flag or enable_env:
        return

    skip_google = pytest.mark.skip(
        reason=("Skipping @google tests. Enable with --enable-google-tests or set "
                "ENABLE_GOOGLE_TESTS=true. (Requires AUTH_MODE=OIDC, GOOGLE_AUDIENCE, GOOGLE_TEST_ID_TOKEN.)")
    )
    for item in items:
        if "google" in item.keywords:
            item.add_marker(skip_google)

# ============ Fixtures ============
@pytest.fixture(scope="session")
def base_client() -> TestClient:
    return TestClient(app)

@pytest.fixture
def authed_client(base_client: TestClient) -> TestClient:
    """
    Adaptive auth client:
      - HS256: returns HS256 dev-token client
      - OIDC : returns Google OIDC client (requires enable + env); else skip
    """
    if AUTH_MODE == "HS256":
        from app.auth import make_dev_token
        tok = make_dev_token(scope="series:read analyze:run")
        c = TestClient(app)
        c.headers.update({"Authorization": f"Bearer {tok}"})
        print(f"[authed_client] HS256 token = { _mask(tok) }")
        return c

    # OIDC branch
    enable_flag = pytest.config.getoption("--enable-google-tests") if hasattr(pytest, "config") else False
    enable_env = os.getenv("ENABLE_GOOGLE_TESTS", "").lower() in ("1", "true", "yes", "on")
    if not (enable_flag or enable_env):
        pytest.skip("OIDC tests disabled: use --enable-google-tests or set ENABLE_GOOGLE_TESTS=true")

    if not _has_google_env():
        pytest.skip("Missing OIDC env (AUTH_MODE=OIDC, GOOGLE_AUDIENCE, GOOGLE_TEST_ID_TOKEN).")

    # Exchange id_token -> internal tokens
    r = base_client.post("/auth/google/exchange", json={"id_token": GOOGLE_TEST_ID_TOKEN})
    assert r.status_code == 200, f"exchange failed: {r.status_code} {r.text}"
    body = r.json()
    access = body["access_token"]

    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {access}"})
    print(f"[authed_client] OIDC access = { _mask(access) }")
    return c

@pytest.fixture(scope="session")
def google_tokens(base_client: TestClient) -> Tuple[str, str | None]:
    if not _has_google_env():
        pytest.skip("Missing OIDC env (AUTH_MODE=OIDC, GOOGLE_AUDIENCE, GOOGLE_TEST_ID_TOKEN).")

    r = base_client.post("/auth/google/exchange", json={"id_token": GOOGLE_TEST_ID_TOKEN})
    assert r.status_code == 200, f"exchange failed: {r.status_code} {r.text}"
    body = r.json()
    access = body["access_token"]
    refresh = body.get("refresh_token")
    print(f"[google_tokens] access={_mask(access)}, refresh={_mask(refresh)}")
    return access, refresh

@pytest.fixture
def google_authed_client(authed_client: TestClient) -> TestClient:
    """
    Wrapper so tests using google_authed_client still run in HS256 mode.
    In HS256, this returns the HS256 authed client.
    In OIDC, it returns the OIDC authed client (same as authed_client above).
    """
    return authed_client
