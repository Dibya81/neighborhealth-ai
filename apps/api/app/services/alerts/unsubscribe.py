"""Opting out of alerts.

Two routes, because an alert is only ethical if the person can always stop it:
  * email: every message carries a signed one-click link (no login needed),
  * SMS / WhatsApp: replying STOP (handled by the Twilio inbound webhook) switches off every
    subscription registered to that phone number.
"""
from __future__ import annotations

import hashlib
import hmac
import re

from app import db
from app.settings import get_settings

STOP_WORDS = {"stop", "stopall", "unsubscribe", "cancel", "end", "quit"}


def make_token(subscription_id: str) -> str:
    sig = hmac.new(get_settings().jwt_secret.encode(), f"unsub:{subscription_id}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{subscription_id}.{sig}"


def verify_token(token: str) -> str | None:
    sub_id, _, sig = (token or "").partition(".")
    if not sub_id or not sig:
        return None
    return sub_id if hmac.compare_digest(make_token(sub_id), f"{sub_id}.{sig}") else None


def unsubscribe_link(subscription_id: str) -> str:
    return f"{get_settings().public_api_url}/v2/alerts/unsubscribe?token={make_token(subscription_id)}"


def deactivate(subscription_id: str) -> bool:
    row = db.fetchone("SELECT id FROM subscriptions WHERE id = ?", (subscription_id,))
    if row:
        db.update("subscriptions", subscription_id, {"active": 0})
    return bool(row)


def normalise_phone(raw: str) -> str:
    """'whatsapp:+9198...' / '+91 98...' -> '+9198...'"""
    return "+" + re.sub(r"\D", "", raw.split(":")[-1])


def is_stop(body: str) -> bool:
    return (body or "").strip().lower() in STOP_WORDS


def deactivate_phone(phone: str) -> int:
    """Switch off every active subscription for this number. Returns how many were switched off."""
    target = normalise_phone(phone)
    n = 0
    for s in db.fetchall("SELECT id, destination_phone FROM subscriptions WHERE active = 1 AND destination_phone IS NOT NULL"):
        if normalise_phone(s["destination_phone"]) == target:
            db.update("subscriptions", s["id"], {"active": 0})
            n += 1
    return n


def valid_twilio_signature(url: str, params: dict, signature: str) -> bool:
    """Twilio signs URL + sorted POST params with the account auth token (HMAC-SHA1, base64)."""
    import base64
    token = get_settings().twilio_token
    if not token:
        return False
    data = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    expected = base64.b64encode(hmac.new(token.encode(), data.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(expected, signature or "")
