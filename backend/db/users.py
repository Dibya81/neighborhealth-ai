import json
from typing import Optional
from db.client import get_supabase
from utils.logger import get_logger

logger = get_logger(__name__)


def upsert_user(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    home_ward_id: Optional[str] = None,
    health_conditions: Optional[list] = None,
    saved_locations: Optional[list] = None,
) -> dict:
    sb = get_supabase()
    payload: dict = {"name": name}
    if email:                                payload["email"]             = email
    if phone:                                payload["phone"]             = phone
    if lat is not None:                      payload["lat"]               = lat
    if lng is not None:                      payload["lng"]               = lng
    if home_ward_id:                         payload["home_ward_id"]      = home_ward_id
    if health_conditions is not None:        payload["health_conditions"] = health_conditions
    if saved_locations is not None:          payload["saved_locations"]   = json.dumps(saved_locations)

    if email:
        result = sb.table("users").upsert(payload, on_conflict="email").execute()
    else:
        result = sb.table("users").insert(payload).execute()

    if not result.data:
        logger.error("Failed to upsert user: %s", result)
        raise Exception("Failed to upsert user")

    return result.data[0]


def save_ai_suggestion(
    user_id: str,
    ward_id: str,
    disease_id: str,
    message: str,
    response: str,
    context: Optional[dict] = None,
) -> None:
    sb = get_supabase()
    sb.table("ai_suggestions").insert({
        "user_id":    user_id,
        "ward_id":    ward_id,
        "disease_id": disease_id,
        "message":    message,
        "response":   response,
        "context":    context or {},
    }).execute()


def get_ai_history(user_id: str, limit: int = 20) -> list[dict]:
    sb = get_supabase()
    result = (
        sb.table("ai_suggestions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data
