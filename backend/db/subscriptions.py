from __future__ import annotations
from typing import Optional
from db.client import get_supabase
from utils.logger import get_logger

logger = get_logger(__name__)


def upsert_subscription(ward_id: str, contact: str, contact_type: str, 
                        threshold: int = 70, user_id: str = None, 
                        name: str = None, email: str = None, 
                        notify_diseases: list = None) -> dict:
    """
    Creates or re-activates a subscription.
    Idempotent: if (ward_id, contact) already exists, updates info.
    """
    sb = get_supabase()
    payload = {
        "ward_id": ward_id,
        "contact": contact,
        "contact_type": contact_type,
        "threshold": threshold,
        "user_id": user_id,
        "name": name,
        "email": email,
        "notify_diseases": notify_diseases or ["dengue"],
        "active": True,
    }
    result = (
        sb.table("subscriptions")
        .upsert(payload, on_conflict="ward_id,contact")
        .execute()
    )
    return result.data[0]


def cancel_subscription(subscription_id: str) -> Optional[dict]:
    """Soft-delete: sets active=False. Returns updated row or None."""
    sb = get_supabase()
    result = (
        sb.table("subscriptions")
        .update({"active": False})
        .eq("id", subscription_id)
        .execute()
    )
    return result.data[0] if result.data else None


def get_active_subscriptions_for_wards(ward_ids: list[str]) -> list[dict]:
    """
    Returns all active subscriptions for a list of ward IDs.
    Called by alert dispatcher after daily pipeline to find who to notify.
    """
    sb = get_supabase()
    result = (
        sb.table("subscriptions")
        .select("id, ward_id, contact, contact_type, threshold, notify_diseases")
        .in_("ward_id", ward_ids)
        .eq("active", True)
        .execute()
    )
    return result.data


def log_alert_sent(subscription_id: str, ward_id: str,
                   risk_score: float, channel: str, disease_id: str = "dengue") -> None:
    """Records a sent alert — used to deduplicate (no double alerts per disease per day)."""
    sb = get_supabase()
    sb.table("alert_log").insert({
        "subscription_id": subscription_id,
        "ward_id": ward_id,
        "risk_score": risk_score,
        "channel": channel,
        "disease_id": disease_id
    }).execute()


def already_alerted_today(subscription_id: str, disease_id: str = "dengue") -> bool:
    """
    Returns True if this subscription already received an alert for THIS disease today.
    Prevents duplicate messages on pipeline re-runs.
    """
    from datetime import date
    sb = get_supabase()
    today = date.today().isoformat()
    result = (
        sb.table("alert_log")
        .select("id")
        .eq("subscription_id", subscription_id)
        .eq("disease_id", disease_id)
        .gte("sent_at", today)
        .limit(1)
        .execute()
    )
    return len(result.data) > 0
