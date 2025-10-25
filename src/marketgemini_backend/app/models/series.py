from pathlib import Path
import json
DATA_DIR = (Path(__file__).resolve().parent.parent / "data" / "public" / "series")
def load_series(asset: str):
    path = DATA_DIR / f"{asset.lower()}.json"
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    series = obj["series"]
    meta = obj.get("meta", {})
    return series, meta