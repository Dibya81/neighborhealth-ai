from __future__ import annotations
from typing import Optional
from db.client import get_supabase
from utils.logger import get_logger

logger = get_logger("DB")
# ... existing ...


def get_all_wards() -> list[dict]:
    """
    Returns all 198 BBMP wards (id, name, constituency, population_density).
    Used by the search autocomplete endpoint.
    Result is stable — cache at the API layer for 24 hours.
    """
    sb = get_supabase()
    result = (
        sb.table("wards")
        .select("id, name, constituency, population_density, area_sqkm")
        .order("id")
        .execute()
    )
    return result.data


def get_ward_by_id(ward_id: str) -> Optional[dict]:
    """Returns a single ward or None if not found."""
    sb = get_supabase()
    result = (
        sb.table("wards")
        .select("*")
        .eq("id", ward_id)
        .single()
        .execute()
    )
    return result.data


def ward_exists(ward_id: str) -> bool:
    """Quick existence check — used in report/subscription validation."""
    return get_ward_by_id(ward_id) is not None
