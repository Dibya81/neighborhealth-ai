from __future__ import annotations
import csv
from pathlib import Path
from typing import Optional
from db.client import get_supabase
from utils.logger import get_logger

logger = get_logger("DB")

WARDS_CSV = Path(__file__).parent.parent / "data" / "processed" / "bbmp_198_wards_demographics.csv"


def _load_local_wards() -> list[dict]:
    if not WARDS_CSV.exists():
        return []
    wards = []
    try:
        with open(WARDS_CSV, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                wards.append({
                    "id": str(r.get("ward_id")),
                    "name": r.get("ward_name"),
                    "constituency": r.get("constituency", ""),
                    "population_density": float(r["population_density"]) if r.get("population_density") else 0.0,
                    "area_sqkm": float(r["area_sqkm"]) if r.get("area_sqkm") else 0.0,
                    "lat": float(r["lat"]) if r.get("lat") else 12.9716,
                    "lng": float(r["lng"]) if r.get("lng") else 77.5946,
                })
    except Exception as e:
        logger.error("Failed loading local wards CSV: %s", e)
    return wards


def get_all_wards() -> list[dict]:
    """
    Returns all 198 BBMP wards (id, name, constituency, population_density).
    Used by the search autocomplete endpoint.
    Result is stable — cache at the API layer for 24 hours.
    """
    try:
        sb = get_supabase()
        result = (
            sb.table("wards")
            .select("id, name, constituency, population_density, area_sqkm")
            .order("id")
            .execute()
        )
        if result.data and len(result.data) > 0:
            return result.data
    except Exception as e:
        logger.warning("Database unavailable (%s); using authentic local BBMP 198 wards dataset", e)

    return _load_local_wards()


def get_ward_by_id(ward_id: str) -> Optional[dict]:
    """
    Returns a single ward dictionary or None if the ward does not exist.
    Distinguishes nonexistent records (returns None) from real database connection failures (raises).
    """
    if not ward_id or not str(ward_id).strip():
        return None

    sb = get_supabase()
    try:
        # Use limit(1) to safely handle nonexistent wards without PGRST116 exception
        result = (
            sb.table("wards")
            .select("*")
            .eq("id", str(ward_id).strip())
            .limit(1)
            .execute()
        )
        if result.data and len(result.data) > 0:
            return result.data[0]
        return None
    except Exception as e:
        err_str = str(e)
        if "PGRST116" in err_str or "0 rows" in err_str:
            return None
        logger.error("Database error querying ward %s: %s", ward_id, e)
        raise


def ward_exists(ward_id: str) -> bool:
    """
    Quick existence check — used in report and subscription validation.
    Returns False for missing wards, raises for connection/auth failures.
    """
    if not ward_id or not str(ward_id).strip():
        return False
    sb = get_supabase()
    try:
        result = (
            sb.table("wards")
            .select("id")
            .eq("id", str(ward_id).strip())
            .limit(1)
            .execute()
        )
        return bool(result.data and len(result.data) > 0)
    except Exception as e:
        err_str = str(e)
        if "PGRST116" in err_str or "0 rows" in err_str:
            return False
        logger.error("Database error checking ward existence %s: %s", ward_id, e)
        raise

