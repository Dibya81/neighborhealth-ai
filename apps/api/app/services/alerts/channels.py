"""Delivery channels: WhatsApp + SMS (Twilio REST API) and email (SMTP).
With ALERTS_DRY_RUN=true (the default) messages are written to data/v2/outbox.log instead of being sent."""
from __future__ import annotations

import base64
import json
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage

from app import db
from app.settings import REPO_ROOT, get_settings


class DeliveryError(Exception):
    pass


def _dry(channel: str, to: str, subject: str, body: str) -> None:
    log = REPO_ROOT / "data" / "v2" / "outbox.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": db.now(), "channel": channel, "to": to, "subject": subject, "body": body},
                           ensure_ascii=False) + "\n")


def _twilio(to: str, from_: str, body: str) -> None:
    s = get_settings()
    if not (s.twilio_sid and s.twilio_token and from_):
        raise DeliveryError("Twilio is not configured")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{s.twilio_sid}/Messages.json"
    data = urllib.parse.urlencode({"To": to, "From": from_, "Body": body}).encode()
    auth = base64.b64encode(f"{s.twilio_sid}:{s.twilio_token}".encode()).decode()
    req = urllib.request.Request(url, data=data, headers={"Authorization": f"Basic {auth}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status >= 300:
                raise DeliveryError(f"Twilio HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        raise DeliveryError(f"Twilio HTTP {e.code}: {e.read()[:200]!r}")


def send(channel: str, to: str, subject: str, body: str) -> None:
    s = get_settings()
    if not to:
        raise DeliveryError(f"no destination for {channel}")
    if s.alerts_dry_run:
        return _dry(channel, to, subject, body)
    if channel == "sms":
        return _twilio(to, s.twilio_sms_from, body)
    if channel == "whatsapp":
        return _twilio(f"whatsapp:{to}", f"whatsapp:{s.twilio_whatsapp_from}" if s.twilio_whatsapp_from else None, body)
    if channel == "email":
        if not (s.smtp_user and s.smtp_password):
            raise DeliveryError("SMTP is not configured")
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = s.smtp_user, to, subject
        msg.set_content(body)
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
            smtp.starttls()
            smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return
    raise DeliveryError(f"unknown channel {channel}")
