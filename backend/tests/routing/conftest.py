# backend/tests/conftest.py

import sys
from pathlib import Path

# This file ensures that 'backend' is on sys.path so that 'import app' works.

ROOT = Path(__file__).resolve().parents[2]  # C:\jay\ProjectAI
BACKEND = ROOT / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
