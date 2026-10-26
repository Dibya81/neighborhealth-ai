"""Citizen breeding-spot reports: intake checks, duplicate merging, spam handling, trust scores.

Pipeline for a new report:
  1. hard checks: inside the city, image is a real image, per-user daily limit
  2. perceptual hash (dHash) of the photo
  3. duplicate check: same/similar photo within 50 m and 14 days -> status "duplicate" (merged)
     the same photo reused at a *different* place -> spam signal
  4. vision check (zero-shot CLIP) -> likely / uncertain / unlikely
  5. status: pending (goes to the officials' review queue). Low-trust reporters' "unlikely" photos
     are marked spam automatically; everything else is reviewed by a human.
Trust score per reporter = Beta(1 + verified, 1 + rejected + spam) posterior mean.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageOps, UnidentifiedImageError

from app import db
from app.geo import distance_m, in_city, ward_at
from app.services.vision import vision
from app.settings import get_settings
from pipeline.config import load_city

CATEGORIES = ("container", "tyre", "drain", "construction", "garbage", "other")


class ReportRejected(Exception):
    pass


# ------------------------------------------------------------------ hashing
def dhash(img: Image.Image, size: int = 8) -> str:
    g = ImageOps.exif_transpose(img).convert("L").resize((size + 1, size), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            left, right = px[row * (size + 1) + col], px[row * (size + 1) + col + 1]
            bits = (bits << 1) | (left > right)
    return f"{bits:016x}"


def hamming(a: str, b: str) -> int:
    return bin(int(a, 16) ^ int(b, 16)).count("1")


# ------------------------------------------------------------------ trust
def trust_score(user_id: str | None) -> dict:
    if not user_id:
        return {"score": 0.5, "verified": 0, "rejected": 0, "total": 0}
    rows = db.fetchall("SELECT status, COUNT(*) AS n FROM reports WHERE user_id = ? GROUP BY status", (user_id,))
    c = {r["status"]: int(r["n"]) for r in rows}
    verified, bad = c.get("verified", 0), c.get("rejected", 0) + c.get("spam", 0)
    return {"score": round((1 + verified) / (2 + verified + bad), 3), "verified": verified,
            "rejected": bad, "total": sum(c.values())}


# ------------------------------------------------------------------ intake
@dataclass
class IntakeResult:
    report: dict
    flags: list[str] = field(default_factory=list)


def create_report(user: dict | None, lat: float, lon: float, category: str, description: str | None,
                  photo_bytes: bytes, filename: str) -> IntakeResult:
    cfg = load_city()["reports"]
    s = get_settings()
    flags: list[str] = []
    if category not in CATEGORIES:
        raise ReportRejected(f"category must be one of {CATEGORIES}")
    if not in_city(lat, lon):
        raise ReportRejected("location is outside the city")
    if len(photo_bytes) > s.max_upload_mb * 1024 * 1024:
        raise ReportRejected(f"photo larger than {s.max_upload_mb} MB")
    try:
        img = Image.open(io.BytesIO(photo_bytes))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise ReportRejected("file is not a valid image")
    if min(img.size) < 200:
        raise ReportRejected("photo is too small; please take a clear photo")

    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    if user:
        n_today = db.fetchone("SELECT COUNT(*) AS n FROM reports WHERE user_id = ? AND created_at >= ?", (user["id"], since))["n"]
        if n_today >= cfg["max_per_user_per_day"]:
            raise ReportRejected("daily report limit reached, thank you for helping!")

    h = dhash(img)
    window = (datetime.now(timezone.utc) - timedelta(days=cfg["duplicate_window_days"])).isoformat()
    dlat = cfg["duplicate_radius_m"] / 111_000 * 3
    nearby = db.fetchall(
        "SELECT id, lat, lon, photo_hash, user_id, created_at FROM reports "
        "WHERE created_at >= ? AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ? AND status != 'spam'",
        (window, lat - dlat, lat + dlat, lon - dlat * 1.1, lon + dlat * 1.1))
    duplicate_of = None
    for r in nearby:
        close = distance_m(lat, lon, r["lat"], r["lon"]) <= cfg["duplicate_radius_m"]
        similar = r["photo_hash"] and hamming(h, r["photo_hash"]) <= 10
        if close and (similar or (user and r["user_id"] == user["id"])):
            duplicate_of = r["id"]
            flags.append("duplicate_nearby")
            break
    reused = db.fetchone("SELECT id, lat, lon FROM reports WHERE photo_hash = ? LIMIT 1", (h,))
    if reused and not duplicate_of and distance_m(lat, lon, reused["lat"], reused["lon"]) > 500:
        flags.append("photo_reused_elsewhere")

    v = vision.check(img)
    if v.label == "unlikely":
        flags.append("vision_unlikely")
    trust = trust_score(user["id"] if user else None)

    status = "pending"
    if duplicate_of:
        status = "duplicate"
    elif "photo_reused_elsewhere" in flags or (v.label == "unlikely" and trust["total"] >= 5 and trust["score"] < 0.3):
        status = "spam"

    rid = db.new_id()
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "jpg").lower()[:5]
    photo_path = s.upload_dir / "reports" / f"{rid}.{ext if ext in ('jpg', 'jpeg', 'png', 'webp', 'heic') else 'jpg'}"
    photo_path.parent.mkdir(parents=True, exist_ok=True)
    clean = ImageOps.exif_transpose(img).convert("RGB")   # re-encode: strips EXIF (incl. GPS) for privacy
    clean.thumbnail((1600, 1600))
    clean.save(photo_path.with_suffix(".jpg"), "JPEG", quality=85)

    report = {"id": rid, "user_id": user["id"] if user else None, "lat": lat, "lon": lon, "ward_id": ward_at(lat, lon),
              "category": category, "description": (description or "")[:500], "photo_path": photo_path.with_suffix(".jpg").name,
              "photo_hash": h, "vision_label": v.label, "vision_score": v.score, "status": status,
              "duplicate_of": duplicate_of, "flags": flags, "created_at": db.now()}
    db.insert("reports", report)
    return IntakeResult(report, flags)


def review(report_id: str, reviewer: dict, decision: str, create_task: bool = True) -> dict:
    if decision not in ("verified", "rejected", "spam"):
        raise ReportRejected("decision must be verified, rejected or spam")
    r = db.fetchone("SELECT * FROM reports WHERE id = ?", (report_id,))
    if not r:
        raise ReportRejected("report not found")
    db.update("reports", report_id, {"status": decision, "reviewed_by": reviewer["id"], "reviewed_at": db.now()})
    task = None
    if decision == "verified" and create_task:
        from app.services.tasks import create_task as _create_task
        task = _create_task(lat=r["lat"], lon=r["lon"], ward_id=r["ward_id"], report_id=report_id,
                            kind="source_reduction", priority=2, actor=reviewer["id"])
    return {"report_id": report_id, "status": decision, "task": task}


def public_report(r: dict) -> dict:
    """What anyone may see: no user id, location rounded to ~100 m."""
    return {"id": r["id"], "lat": round(r["lat"], 3), "lon": round(r["lon"], 3), "ward_id": r["ward_id"],
            "category": r["category"], "status": r["status"], "created_at": r["created_at"]}


def verified_reports_by_ward(days: int = 28) -> dict[str, int]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.fetchall("SELECT ward_id, COUNT(*) AS n FROM reports WHERE status = 'verified' AND created_at >= ? "
                       "AND ward_id IS NOT NULL GROUP BY ward_id", (since,))
    return {r["ward_id"]: int(r["n"]) for r in rows}
