"""Read-only access to the published forecast bundle (data/v2/forecasts/latest.json), reloaded when it changes."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from pipeline.config import get_paths

BAND_ORDER = ["low", "moderate", "high", "very_high"]
_lock = threading.Lock()
_cache: dict = {"mtime": None, "bundle": None}


def bundle_path() -> Path:
    return get_paths().root / "forecasts" / "latest.json"


def get_bundle() -> dict | None:
    p = bundle_path()
    if not p.exists():
        return None
    mtime = p.stat().st_mtime
    with _lock:
        if _cache["mtime"] != mtime:
            _cache["bundle"] = json.loads(p.read_text())
            _cache["mtime"] = mtime
            _cache["index"] = {
                h: {w["ward_id"]: w for w in rows} for h, rows in _cache["bundle"].get("wards", {}).items()
                if isinstance(rows, list)
            }
        return _cache["bundle"]


def ward_estimate(ward_id: str, horizon: int = 1) -> dict | None:
    if get_bundle() is None:
        return None
    return _cache.get("index", {}).get(str(horizon), {}).get(ward_id)


def band_rank(band: str | None) -> int:
    return BAND_ORDER.index(band) if band in BAND_ORDER else -1


def freshness_days() -> float | None:
    b = get_bundle()
    if not b:
        return None
    # Age of the DATA, not of the file: a forecast regenerated today from bulletins that end in 2024
    # is not fresh. origin_week is the last week of real observations behind the forecast.
    origin = b.get("origin_week")
    if origin:
        since = datetime.fromisoformat(origin).replace(tzinfo=timezone.utc)
    else:
        since = datetime.fromisoformat(b["generated_at"])
    return (datetime.now(timezone.utc) - since).total_seconds() / 86400
