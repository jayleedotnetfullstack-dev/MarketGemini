# src/marketgemini_backend/app/services/series.py
from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Tuple

def _project_root() -> Path:
    """
    Locate the project root dynamically.
    This file lives at: src/marketgemini_backend/app/services/series.py
    -> project root is four levels up (../../../../)
    """
    return Path(__file__).resolve().parents[4]

def _data_root() -> Path:
    """
    Return the <project_root>/data folder.
    Raises if not found, to avoid silent fallback.
    """
    root = _project_root() / "data"
    if not root.exists():
        raise FileNotFoundError(f"Data folder not found: {root}")
    return root

def load_series(name: str) -> Tuple[List[Tuple[str, float]], Dict]:
    """
    Load a named series from data/public/series/<name>.json
    Returns: (series: list[(timestamp, value)], meta: dict)
    """
    path = _data_root() / "public" / "series" / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Series not found: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    series = obj.get("series") or obj.get("data") or []
    meta = obj.get("meta") or {}
    return series, meta
