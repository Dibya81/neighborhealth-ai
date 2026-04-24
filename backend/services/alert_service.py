from utils.logger import get_logger
from config import get_settings

logger = get_logger("ALERT")


def is_ward_above_threshold(risk_score: float, subscriber_threshold: int = None) -> bool:
    settings = get_settings()
    threshold = subscriber_threshold if subscriber_threshold is not None else settings.alert_threshold
    return float(risk_score) >= float(threshold)


def get_elevated_wards(all_scores: list[dict], threshold: int = None) -> list[dict]:
    settings = get_settings()
    cutoff = threshold if threshold is not None else settings.alert_threshold
    return [s for s in all_scores if float(s.get("risk_score", 0)) >= float(cutoff)]


def build_alert_message(ward_name: str, risk_score: float, risk_level: str, disease_name: str) -> str:
    level_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk_level, "⚠️")
    return (
        f"NeighborHealth Alert {level_emoji}\n"
        f"Disease: {disease_name}\n"
        f"Area: {ward_name}\n"
        f"Risk: {risk_level.upper()} ({int(risk_score)}/100)\n"
        f"Take precautions today.\n"
        f"Map: neighborhealth.app"
    )


def dispatch_to_subscriber(
    subscription: dict,
    ward_name: str,
    disease_name: str,
    risk_score: float,
    risk_level: str,
) -> dict:
    from integrations.twilio import notify_user
    return notify_user(subscription, ward_name, disease_name, risk_score, risk_level)
