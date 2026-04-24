from datetime import datetime, timedelta, timezone
from typing import Optional
from db.client import get_supabase
from utils.logger import get_logger

logger = get_logger(__name__)


def insert_report(ward_id: str, lat: float, lng: float,
                  description: Optional[str], photo_url: Optional[str],
                  ip_hash: Optional[str]) -> dict:
    """Creates a new breeding spot report. Returns the inserted row."""
    sb = get_supabase()
    payload = {
        "ward_id": ward_id,
        "lat": lat,
        "lng": lng,
        "description": description,
        "photo_url": photo_url,
        "ip_hash": ip_hash,
        "status": "pending",
    }
    result = sb.table("breeding_reports").insert(payload).execute()
    return result.data[0]


def get_reports_for_ward(ward_id: str, days: int = 7) -> list:
    """Returns recent reports for a ward — shown in the ward detail panel."""
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = (
        sb.table("breeding_reports")
        .select("id, lat, lng, description, photo_url, status, reported_at")
        .eq("ward_id", ward_id)
        .neq("status", "spam")
        .gte("reported_at", since)
        .order("reported_at", desc=True)
        .execute()
    )
    return result.data


def get_report_counts_per_ward(days: int = 7) -> dict[str, int]:
    """
    Returns a dict of ward_id → report_count for the last N days.
    Called during feature engineering in the daily pipeline.
    """
    sb = get_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = (
        sb.table("breeding_reports")
        .select("ward_id")
        .neq("status", "spam")
        .gte("reported_at", since)
        .execute()
    )
    counts = {}
    for row in result.data:
        wid = row["ward_id"]
        counts[wid] = counts.get(wid, 0) + 1
    return counts
