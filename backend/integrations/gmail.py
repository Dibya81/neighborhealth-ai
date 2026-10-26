"""
Gmail Integration Module

Delegates email alerting to the unified notification service.
"""
from services.notification_service import send_gmail_alert

__all__ = ["send_gmail_alert"]
