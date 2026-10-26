"""Nearby health facilities from OpenStreetMap (© OpenStreetMap contributors, ODbL).

    python -m app.services.clinics fetch     # download hospitals/clinics in the city bbox via Overpass
"""
from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from functools import lru_cache

from app.geo import distance_m
from pipeline.config import get_paths, load_city

OVERPASS = "https://overpass-api.de/api/interpreter"


def _path():
    return get_paths().processed / "clinics.json"


def fetch() -> int:
    x0, y0, x1, y1 = load_city()["geography"]["bbox"]
    q = f"""[out:json][timeout:120];
    (nwr["amenity"~"hospital|clinic|doctors"]({y0},{x0},{y1},{x1});
     nwr["healthcare"~"hospital|clinic|centre|laboratory"]({y0},{x0},{y1},{x1}););
    out center tags;"""
    req = urllib.request.Request(OVERPASS, data=urllib.parse.urlencode({"data": q}).encode(),
                                 headers={"User-Agent": "NeighborHealth/2.0"})
    with urllib.request.urlopen(req, timeout=180) as resp:
        els = json.loads(resp.read())["elements"]
    out = []
    for e in els:
        t = e.get("tags", {})
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        if not (lat and lon and t.get("name")):
            continue
        out.append({"id": f"{e['type']}/{e['id']}", "name": t["name"], "lat": lat, "lon": lon,
                    "kind": t.get("amenity") or t.get("healthcare"), "phone": t.get("phone") or t.get("contact:phone"),
                    "emergency": t.get("emergency") == "yes", "operator_type": t.get("operator:type"),
                    "address": ", ".join(v for k, v in t.items() if k.startswith("addr:") and v)})
    _path().write_text(json.dumps(out))
    _all.cache_clear()
    return len(out)


@lru_cache
def _all() -> list[dict]:
    p = _path()
    return json.loads(p.read_text()) if p.exists() else []


def nearest(lat: float, lon: float, n: int = 5, kind: str | None = None) -> list[dict]:
    # Copy: _all() is a shared cache, and concurrent requests must not overwrite each other's distances.
    items = [{**c, "distance_m": round(distance_m(lat, lon, c["lat"], c["lon"]))}
             for c in _all() if not kind or c["kind"] == kind]
    return sorted(items, key=lambda c: (not c["emergency"] if kind == "hospital" else 0, c["distance_m"]))[:n]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        print(f"{fetch()} facilities saved to {_path()}")
