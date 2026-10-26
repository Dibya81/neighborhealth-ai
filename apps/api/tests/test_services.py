"""Unit tests for API services that don't need a running server or database."""
from datetime import datetime, timezone

from PIL import Image

from app.services.alerts.engine import deliver_after
from app.services.alerts.templates import render
from app.services.assistant.explain import template, verify
from app.services.reports import dhash, hamming
from app.services.routing import Stop, _heuristic, travel_matrix

FACTS = {"ward": "Jayanagar", "band": "high", "rate_per_100k": 6.4, "rate_interval": [3.1, 11.0], "uncertainty": "medium",
         "city_cases": 420.0, "city_interval": [310.0, 560.0], "week_end": "2026-11-01",
         "factors": [{"label": "Rainfall in recent weeks", "factor": "rain", "direction": "up", "effect_pct": 34.0}]}


def test_templates_render_in_all_languages():
    for lang in ("en", "kn", "hi"):
        subject, body = render(lang, "high", "home", "Jayanagar", "2026-11-01", "https://x")
        assert "Jayanagar" in body and "https://x" in body and "STOP" in body and subject


def test_quiet_hours_hold_night_alerts_until_morning():
    night = datetime(2026, 10, 25, 17, 30, tzinfo=timezone.utc)      # 23:00 IST
    held = deliver_after("21:00", "08:00", night)
    assert held > night
    assert held.isoformat().startswith("2026-10-26T02:30")               # 08:00 IST
    day = datetime(2026, 10, 25, 6, 0, tzinfo=timezone.utc)            # 11:30 IST
    assert deliver_after("21:00", "08:00", day) == day


def test_dhash_finds_near_duplicates():
    a = Image.linear_gradient("L").resize((300, 300)).convert("RGB")
    b = a.resize((280, 280))
    c = a.rotate(-90)   # gradient now darkens left-to-right; rotate(90) would hash to all zeros like `a`
    assert hamming(dhash(a), dhash(b)) <= 6
    assert hamming(dhash(a), dhash(c)) > 10


def test_explanation_verifier_catches_invented_numbers_and_causes():
    ok, _ = verify("Risk in Jayanagar is high, about 6.4 cases per 100,000, mainly because of rainfall (+34%).", FACTS)
    assert ok
    bad, problems = verify("Risk is high because humidity rose 72% and 900 cases are expected.", FACTS)
    assert not bad and any("humidity" in p for p in problems) and any("900" in p for p in problems)
    assert "Jayanagar" in template(FACTS)


def test_route_heuristic_visits_every_stop_within_shift():
    depot = (12.97, 77.59)
    stops = [Stop(str(i), 12.95 + 0.01 * (i % 5), 77.55 + 0.01 * (i // 5)) for i in range(15)]
    pts = [depot] + [(s.lat, s.lon) for s in stops]
    T = travel_matrix(pts)
    import numpy as np
    routes, dropped, _ = _heuristic(T, np.array([0] + [15] * 15, float), np.array([1] + [2] * 15), pts, 2, 600)
    visited = sorted(i for r in routes for i in r)
    assert sorted(visited + list(dropped)) == list(range(1, 16))


def test_alerts_refuse_to_run_on_a_stale_forecast(monkeypatch):
    """A forecast built from old bulletins must never trigger alerts to residents."""
    from app.services.alerts import engine
    monkeypatch.setattr(engine, "get_bundle", lambda: {"forecast": []})
    monkeypatch.setattr(engine, "freshness_days", lambda: 400.0)
    out = engine.evaluate_subscriptions()
    assert out["skipped"] == "forecast_stale" and out["queued"] == 0


# ---------------------------------------------------------------- opting out of alerts
def test_every_alert_tells_the_reader_how_to_stop_it():
    from app.services.alerts.templates import render
    for lang in ("en", "kn", "hi"):
        _, email = render(lang, "high", "home", "Jayanagar", "2026-11-01", "https://x", channel="email",
                          unsubscribe_link="https://api/unsub?token=T")
        _, sms = render(lang, "high", "home", "Jayanagar", "2026-11-01", "https://x", channel="sms")
        assert "https://api/unsub?token=T" in email and "STOP" not in email   # email can't be replied to
        assert "STOP" in sms                                                    # SMS / WhatsApp can


def test_unsubscribe_tokens_cannot_be_forged():
    from app.services.alerts import unsubscribe as u
    t = u.make_token("sub123")
    assert u.verify_token(t) == "sub123"
    assert u.verify_token("sub123.deadbeef") is None and u.verify_token("sub124." + t.split(".")[1]) is None
    assert u.verify_token("") is None


def test_stop_replies_are_recognised_and_phone_numbers_normalised():
    from app.services.alerts import unsubscribe as u
    assert all(u.is_stop(w) for w in ("STOP", " stop ", "Unsubscribe", "QUIT")) and not u.is_stop("stop it please")
    assert u.normalise_phone("whatsapp:+91 98765-43210") == u.normalise_phone("+919876543210") == "+919876543210"


def test_twilio_signature_check(monkeypatch):
    import base64, hashlib, hmac
    from app.services.alerts import unsubscribe as u
    monkeypatch.setattr(u, "get_settings", lambda: type("S", (), {"twilio_token": "secret", "jwt_secret": "x"})())
    params = {"From": "+911234567890", "Body": "STOP"}
    url = "https://api.example.org/v2/webhooks/twilio"
    good = base64.b64encode(hmac.new(b"secret", (url + "BodySTOPFrom+911234567890").encode(), hashlib.sha1).digest()).decode()
    assert u.valid_twilio_signature(url, params, good)
    assert not u.valid_twilio_signature(url, params, "forged")
    monkeypatch.setattr(u, "get_settings", lambda: type("S", (), {"twilio_token": None, "jwt_secret": "x"})())
    assert not u.valid_twilio_signature(url, params, good)       # unconfigured webhook accepts nothing
