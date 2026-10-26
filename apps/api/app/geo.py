"""Ward geometry helpers used across the API (pure Python; PostGIS is used for heavy queries in production)."""
from __future__ import annotations

import json
import math
from functools import lru_cache

from ml.wards import _rings, haversine_km, point_in_ring
from pipeline.config import REPO_ROOT, load_city


@lru_cache
def ward_features() -> list[dict]:
    cfg = load_city()
    gj = json.loads((REPO_ROOT / cfg["geography"]["wards_geojson"]).read_text())
    id_key, name_key = cfg["geography"]["ward_id_key"], cfg["geography"]["ward_name_key"]
    feats = []
    for f in gj["features"]:
        rings = _rings(f["geometry"])
        if not rings:
            continue
        xs = [p[0] for r in rings for p in r]
        ys = [p[1] for r in rings for p in r]
        feats.append({"ward_id": str(f["properties"][id_key]), "ward_name": f["properties"][name_key],
                      "rings": rings, "bbox": (min(xs), min(ys), max(xs), max(ys)),
                      "center": (sum(ys) / len(ys), sum(xs) / len(xs))})
    return feats


def ward_name(ward_id: str) -> str:
    return next((f["ward_name"] for f in ward_features() if f["ward_id"] == ward_id), ward_id)


def ward_at(lat: float, lon: float) -> str | None:
    for f in ward_features():
        x0, y0, x1, y1 = f["bbox"]
        if x0 <= lon <= x1 and y0 <= lat <= y1 and any(point_in_ring(lon, lat, r) for r in f["rings"]):
            return f["ward_id"]
    return None


def wards_within(lat: float, lon: float, radius_m: float) -> list[str]:
    """Wards containing the point, plus wards whose boundary comes within the radius (vertex check)."""
    out = set()
    home = ward_at(lat, lon)
    if home:
        out.add(home)
    r_km = radius_m / 1000
    dlat = r_km / 111.0
    dlon = r_km / (111.0 * math.cos(math.radians(lat)))
    for f in ward_features():
        x0, y0, x1, y1 = f["bbox"]
        if x1 < lon - dlon or x0 > lon + dlon or y1 < lat - dlat or y0 > lat + dlat:
            continue
        for ring in f["rings"]:
            if any(haversine_km(lat, lon, p[1], p[0]) <= r_km for p in ring[:: max(1, len(ring) // 60)]):
                out.add(f["ward_id"])
                break
    return sorted(out)


def in_city(lat: float, lon: float) -> bool:
    x0, y0, x1, y1 = load_city()["geography"]["bbox"]
    return x0 <= lon <= x1 and y0 <= lat <= y1


def distance_m(lat1, lon1, lat2, lon2) -> float:
    return float(haversine_km(lat1, lon1, lat2, lon2) * 1000)
