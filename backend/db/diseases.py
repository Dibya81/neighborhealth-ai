from __future__ import annotations
from db.client import get_supabase
from utils.logger import get_logger

logger = get_logger(__name__)

def get_all_diseases() -> list[dict]:
    """Retrieves all registered diseases from the registry."""
    sb = get_supabase()
    result = sb.table("diseases").select("*").execute()
    return result.data

def get_disease_by_id(disease_id: str) -> dict:
    """Retrieves a specific disease by its ID."""
    sb = get_supabase()
    result = sb.table("diseases").select("*").eq("id", disease_id).execute()
    return result.data[0] if result.data else None
