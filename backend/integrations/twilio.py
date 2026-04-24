from config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


def send_sms(to_number: str, message: str) -> dict:
    from twilio.rest import Client

    settings = get_settings()

    if not settings.twilio_account_sid or not settings.twilio_auth_token or not settings.twilio_from_number:
        logger.warning("Twilio credentials not fully configured — SMS to ...%s SKIPPED.", to_number[-4:])
        return {"status": "skipped", "reason": "no_credentials"}

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    msg = client.messages.create(
        body=message,
        from_=settings.twilio_from_number,
        to=to_number,
    )

    logger.info("SMS sent to ...%s | SID: %s | Status: %s", to_number[-4:], msg.sid, msg.status)
    return {"sid": msg.sid, "status": msg.status}


def send_sms_alert(to_number: str, ward_name: str, disease: str, score: float, risk_level: str) -> dict:
    from services.alert_service import build_alert_message
    message = build_alert_message(ward_name, score, risk_level, disease)
    return send_sms(to_number, message)


def notify_user(subscription: dict, ward_name: str, disease_name: str,
                risk_score: float, risk_level: str) -> dict:
    contact_type = subscription.get("contact_type", "")
    contact = subscription.get("contact", "")

    if contact_type == "sms":
        return send_sms_alert(contact, ward_name, disease_name, risk_score, risk_level)
    elif contact_type == "email":
        from services.notification_service import send_gmail_alert
        success = send_gmail_alert(contact, ward_name, disease_name, risk_score)
        return {"status": "sent" if success else "failed"}
    else:
        logger.warning("Unknown contact_type '%s' for subscription %s", contact_type, subscription.get("id"))
        return {"status": "skipped", "reason": f"unknown_contact_type:{contact_type}"}
