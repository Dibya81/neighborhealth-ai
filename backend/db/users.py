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
    if saved_locations is not None:
        if isinstance(saved_locations, str):
            try:
                payload["saved_locations"] = json.loads(saved_locations)
            except Exception:
                payload["saved_locations"] = []
        else:
            payload["saved_locations"] = saved_locations


    try:
        if email:
            result = sb.table("users").upsert(payload, on_conflict="email").execute()
        else:
            result = sb.table("users").insert(payload).execute()

        if result.data and len(result.data) > 0:
            return result.data[0]
    except Exception as e:
        logger.warning("Database unavailable during user upsert (%s); creating authenticated user session", e)
        import uuid
        from datetime import datetime
        user_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, email or name))
        payload["id"] = user_uuid
        payload["created_at"] = datetime.utcnow().isoformat()
        return payload

    raise Exception("Failed to upsert user")


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
