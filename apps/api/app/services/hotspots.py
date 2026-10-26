"""Hotspot detection: DBSCAN with the haversine metric on recent credible reports.

A hotspot = at least `min_reports` reports within `eps_m` metres of each other in the last N days.
Reports are weighted by status (verified counts fully, pending by reporter trust) so one spammer
can't create a hotspot.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from app import db
from app.geo import ward_name
from app.services.reports import trust_score
from pipeline.config import load_city

EARTH_R_M = 6_371_008.8


def detect_hotspots(days: int | None = None) -> list[dict]:
    from sklearn.cluster import DBSCAN
    cfg = load_city()["reports"]
    days = days or cfg["hotspot_window_days"]
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.fetchall("SELECT id, lat, lon, ward_id, status, user_id, created_at FROM reports "
                       "WHERE created_at >= ? AND status IN ('verified', 'pending')", (since,))
    if len(rows) < cfg["hotspot_min_reports"]:
        return []
    trust_cache: dict = {}
    weights = []
    for r in rows:
        if r["status"] == "verified":
            weights.append(1.0)
        else:
            uid = r["user_id"]
            if uid not in trust_cache:
                trust_cache[uid] = trust_score(uid)["score"]
            weights.append(trust_cache[uid])
    coords = np.radians([[r["lat"], r["lon"]] for r in rows])
    labels = DBSCAN(eps=cfg["hotspot_eps_m"] / EARTH_R_M, min_samples=cfg["hotspot_min_reports"],
                    metric="haversine").fit(coords, sample_weight=np.array(weights)).labels_
    out = []
    for lab in sorted(set(labels) - {-1}):
        idx = np.where(labels == lab)[0]
        members = [rows[i] for i in idx]
        lat = float(np.mean([m["lat"] for m in members]))
        lon = float(np.mean([m["lon"] for m in members]))
        radius = max(float(np.max([np.hypot((m["lat"] - lat) * 111_000, (m["lon"] - lon) * 108_000) for m in members])), 30.0)
        wards = [m["ward_id"] for m in members if m["ward_id"]]
        ward = max(set(wards), key=wards.count) if wards else None
        out.append({"id": f"hs-{lab}", "lat": round(lat, 5), "lon": round(lon, 5), "radius_m": round(radius),
                    "reports": len(members), "verified": sum(m["status"] == "verified" for m in members),
                    "weight": round(float(np.sum(np.array(weights)[idx])), 2), "ward_id": ward,
                    "ward_name": ward_name(ward) if ward else None,
                    "latest": max(m["created_at"] for m in members), "report_ids": [m["id"] for m in members]})
    return sorted(out, key=lambda h: (-h["weight"], h["latest"]))
