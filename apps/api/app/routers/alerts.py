from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, EmailStr, Field

from app import db
from app.geo import in_city, ward_name, wards_within
from app.security import current_user, require_role
from app.services.alerts import unsubscribe as unsub
from app.services.alerts.engine import evaluate_subscriptions, fatigue_metrics
from app.settings import get_settings
from app.services.pilot import record_consent
from pipeline.config import load_city

router = APIRouter(prefix="/v2", tags=["alerts"])


class SubscriptionIn(BaseModel):
    label: str = Field(pattern="^(home|office|school|other)$")
    lat: float
    lon: float
    radius_m: int = Field(1000, ge=200, le=5000)
    channels: list[str] = Field(min_length=1)
    phone: str | None = Field(None, pattern=r"^\+\d{8,15}$")
    email: EmailStr | None = None
    language: str = Field("en", pattern="^(en|kn|hi)$")
    quiet_start: str | None = Field("21:00", pattern=r"^\d{2}:\d{2}$")
    quiet_end: str | None = Field("08:00", pattern=r"^\d{2}:\d{2}$")
    threshold_band: str = Field("high", pattern="^(moderate|high|very_high)$")
    consent: bool


def _validate(body: SubscriptionIn) -> None:
    if not body.consent:
        raise HTTPException(400, "Please agree to receive alerts")
    if not set(body.channels) <= {"whatsapp", "sms", "email"}:
        raise HTTPException(422, "channels must be whatsapp, sms and/or email")
    if {"whatsapp", "sms"} & set(body.channels) and not body.phone:
        raise HTTPException(422, "A phone number (with country code, e.g. +91...) is needed for WhatsApp/SMS")
    if "email" in body.channels and not body.email:
        raise HTTPException(422, "An email address is needed for email alerts")
    if not in_city(body.lat, body.lon):
        raise HTTPException(422, f"That place is outside {load_city()['city']['name']}")


def _out(s: dict) -> dict:
    wards = db.loads(s["ward_ids"], [])
    return {**{k: s[k] for k in ("id", "label", "lat", "lon", "radius_m", "language", "quiet_start", "quiet_end",
                                 "threshold_band", "last_band", "created_at")},
            "active": bool(s["active"]), "channels": db.loads(s["channels"], []),
            "wards": [{"ward_id": w, "ward_name": ward_name(w)} for w in wards]}


@router.get("/subscriptions")
def list_subs(user: dict = Depends(current_user)):
    rows = db.fetchall("SELECT * FROM subscriptions WHERE user_id = ? AND active = 1 ORDER BY created_at", (user["id"],))
    return {"subscriptions": [_out(r) for r in rows]}


@router.post("/subscriptions")
def create_sub(body: SubscriptionIn, user: dict = Depends(current_user)):
    _validate(body)
    n = db.fetchone("SELECT COUNT(*) AS n FROM subscriptions WHERE user_id = ? AND active = 1", (user["id"],))["n"]
    if n >= 5:
        raise HTTPException(422, "You can save up to 5 places")
    wards = wards_within(body.lat, body.lon, body.radius_m)
    if not wards:
        raise HTTPException(422, "Couldn't find a ward at that location")
    s = {"id": db.new_id(), "user_id": user["id"], "label": body.label, "lat": body.lat, "lon": body.lon,
         "radius_m": body.radius_m, "ward_ids": wards, "channels": body.channels, "destination_phone": body.phone,
         "destination_email": str(body.email) if body.email else None, "language": body.language,
         "quiet_start": body.quiet_start, "quiet_end": body.quiet_end, "threshold_band": body.threshold_band,
         "active": 1, "created_at": db.now()}
    db.insert("subscriptions", s)
    record_consent(user["id"], "alerts", True)
    return _out(db.fetchone("SELECT * FROM subscriptions WHERE id = ?", (s["id"],)))


@router.delete("/subscriptions/{sub_id}")
def delete_sub(sub_id: str, user: dict = Depends(current_user)):
    s = db.fetchone("SELECT user_id FROM subscriptions WHERE id = ?", (sub_id,))
    if not s or s["user_id"] != user["id"]:
        raise HTTPException(404, "Not found")
    db.update("subscriptions", sub_id, {"active": 0})
    return {"ok": True}


@router.get("/alerts/mine")
def my_alerts(user: dict = Depends(current_user)):
    rows = db.fetchall("SELECT id, ward_id, band, horizon, channel, status, created_at, sent_at, feedback FROM alerts "
                       "WHERE user_id = ? AND status != 'marker' ORDER BY created_at DESC LIMIT 50", (user["id"],))
    return {"alerts": [{**r, "ward_name": ward_name(r["ward_id"]) if r["ward_id"] else None} for r in rows]}


class FeedbackIn(BaseModel):
    feedback: str = Field(pattern="^(useful|not_useful|unsubscribed)$")


@router.post("/alerts/{alert_id}/feedback")
def alert_feedback(alert_id: str, body: FeedbackIn, user: dict = Depends(current_user)):
    a = db.fetchone("SELECT user_id, subscription_id FROM alerts WHERE id = ?", (alert_id,))
    if not a or a["user_id"] != user["id"]:
        raise HTTPException(404, "Not found")
    db.update("alerts", alert_id, {"feedback": body.feedback})
    if body.feedback == "unsubscribed":
        db.update("subscriptions", a["subscription_id"], {"active": 0})
    return {"ok": True}


@router.post("/admin/alerts/run")
def run_alerts(user: dict = Depends(require_role("admin", "official"))):
    return evaluate_subscriptions()


@router.get("/admin/alerts/metrics")
def alert_metrics(days: int = 28, user: dict = Depends(require_role("admin", "official"))):
    return fatigue_metrics(days)


# ---------------------------------------------------------------- opting out
@router.get("/alerts/unsubscribe", response_class=HTMLResponse)
def unsubscribe_by_link(token: str):
    """One-click unsubscribe from an email alert (signed token; no login)."""
    sub_id = unsub.verify_token(token)
    if not sub_id or not unsub.deactivate(sub_id):
        return HTMLResponse("<p>This unsubscribe link is not valid.</p>", status_code=400)
    return HTMLResponse("<p>You have been unsubscribed from NeighborHealth alerts for this place. "
                        "You can turn alerts back on any time in the app.</p>")


@router.post("/webhooks/twilio", response_class=PlainTextResponse, include_in_schema=False)
async def twilio_inbound(request: Request):
    """Twilio calls this when someone replies to an SMS/WhatsApp alert. STOP switches off their alerts."""
    form = dict((await request.form()).items())
    public = get_settings().public_api_url
    url = f"{public}{request.url.path}"
    if not unsub.valid_twilio_signature(url, form, request.headers.get("X-Twilio-Signature", "")):
        raise HTTPException(403, "Invalid signature")
    if unsub.is_stop(form.get("Body", "")) and form.get("From"):
        unsub.deactivate_phone(form["From"])
    return PlainTextResponse('<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="text/xml")
