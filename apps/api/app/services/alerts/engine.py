"""Decide who gets an alert, and when.

For every active subscription (a saved place covering one or more wards):
  1. worst forecast band among its wards for the next `horizons` weeks
  2. alert only on an UPWARD crossing of the user's threshold (hysteresis: no repeat while the
     area stays high; re-arms once it drops below the threshold)
  3. de-duplicate: one alert per subscription per forecast week (unique dedupe_key in the DB)
  4. fatigue cap: at most N alerts per user per 7 days (extra ones are recorded as suppressed)
  5. quiet hours: alerts created at night are held until the quiet period ends (city timezone)
Everything is recorded, including suppressed alerts, so alert fatigue can be measured.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app import db
from app.forecast_store import BAND_ORDER, band_rank, freshness_days, get_bundle, ward_estimate
from app.geo import ward_name
from app.services.alerts.queue import get_queue
from pipeline.config import load_city


def _tz() -> ZoneInfo:
    return ZoneInfo(load_city()["city"]["timezone"])


def deliver_after(quiet_start: str | None, quiet_end: str | None, now_utc: datetime) -> datetime:
    """If `now` falls in quiet hours (e.g. 21:00-08:00 local), return the end of quiet hours (UTC)."""
    if not quiet_start or not quiet_end:
        return now_utc
    tz = _tz()
    local = now_utc.astimezone(tz)
    qs, qe = time.fromisoformat(quiet_start), time.fromisoformat(quiet_end)
    t = local.time()
    in_quiet = (qs <= t or t < qe) if qs > qe else (qs <= t < qe)
    if not in_quiet:
        return now_utc
    end = datetime.combine(local.date(), qe, tzinfo=tz)
    if end <= local:
        end += timedelta(days=1)
    return end.astimezone(timezone.utc)


def worst_band(ward_ids: list[str], horizons: list[int]) -> tuple[str | None, str | None, int | None]:
    best = (None, None, None)
    for h in horizons:
        for w in ward_ids:
            est = ward_estimate(w, h)
            if est and band_rank(est["band"]) > band_rank(best[0]):
                best = (est["band"], w, h)
    return best


def evaluate_subscriptions(now_utc: datetime | None = None) -> dict:
    now_utc = now_utc or datetime.now(timezone.utc)
    bundle = get_bundle()
    if not bundle:
        return {"error": "no forecast published"}
    cfg = load_city()["alerts"]
    # Never warn people from old data: an alert about a week that has long passed is worse than none.
    max_age = cfg.get("max_forecast_age_days", 21)
    age = freshness_days()
    if age is None or age > max_age:
        return {"skipped": "forecast_stale", "forecast_age_days": None if age is None else round(age, 1),
                "max_forecast_age_days": max_age, "evaluated": 0, "queued": 0, "suppressed": 0, "rearmed": 0}
    horizons = cfg["horizons"]
    week_for = {f["horizon"]: f["week_end"] for f in bundle["forecast"]}
    since = (now_utc - timedelta(days=7)).isoformat()
    stats = {"evaluated": 0, "queued": 0, "suppressed": 0, "rearmed": 0}

    for sub in db.fetchall("SELECT * FROM subscriptions WHERE active = 1"):
        stats["evaluated"] += 1
        wards = db.loads(sub["ward_ids"], [])
        band, ward, h = worst_band(wards, horizons)
        threshold = sub["threshold_band"] or cfg["default_threshold_band"]
        above = band_rank(band) >= band_rank(threshold)
        was_above = band_rank(sub["last_band"]) >= band_rank(threshold)
        db.update("subscriptions", sub["id"], {"last_band": band})
        if not above:
            if was_above:
                stats["rearmed"] += 1
            continue
        if was_above:
            continue  # still high: already alerted on the way up (hysteresis)

        week = week_for.get(h, "")
        dedupe_key = f"{sub['id']}:{week}"
        if db.fetchone("SELECT id FROM alerts WHERE dedupe_key = ?", (dedupe_key,)):
            continue
        # one "marker" row per alert event (not per channel); count only events that were actually sent out
        recent = db.fetchone("SELECT COUNT(*) AS n FROM alerts WHERE user_id = ? AND status = 'marker' "
                             "AND reason = 'queued' AND created_at >= ?", (sub["user_id"], since))["n"]
        status, reason = "queued", None
        if recent >= cfg["max_alerts_per_user_per_week"]:
            status, reason = "suppressed", "fatigue_cap"
        when = deliver_after(sub["quiet_start"], sub["quiet_end"], now_utc)
        if status == "queued" and when > now_utc:
            reason = "quiet_hours"
        for channel in db.loads(sub["channels"], ["email"]):
            aid = db.new_id()
            db.insert("alerts", {"id": aid, "subscription_id": sub["id"], "user_id": sub["user_id"], "ward_id": ward,
                                 "band": band, "horizon": h, "dedupe_key": f"{dedupe_key}:{channel}", "channel": channel,
                                 "status": status, "reason": reason, "deliver_after": when.isoformat(),
                                 "created_at": now_utc.isoformat()})
            stats["queued" if status == "queued" else "suppressed"] += 1
        # marker row so the whole subscription-week is de-duplicated regardless of channel count
        db.insert("alerts", {"id": db.new_id(), "subscription_id": sub["id"], "user_id": sub["user_id"],
                             "ward_id": ward, "band": band, "horizon": h, "dedupe_key": dedupe_key, "channel": None,
                             "status": "marker", "reason": status, "created_at": now_utc.isoformat()})
    dispatch_due(now_utc)
    return stats


def dispatch_due(now_utc: datetime | None = None) -> int:
    """Push alerts whose quiet period is over onto the delivery queue."""
    now_utc = now_utc or datetime.now(timezone.utc)
    due = db.fetchall("SELECT id FROM alerts WHERE status = 'queued' AND (deliver_after IS NULL OR deliver_after <= ?)",
                      (now_utc.isoformat(),))
    q = get_queue()
    for a in due:
        db.update("alerts", a["id"], {"status": "dispatched"})
        q.put(a["id"])
    return len(due)


def fatigue_metrics(days: int = 28) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.fetchall("SELECT user_id, status, reason, feedback FROM alerts WHERE created_at >= ? AND status != 'marker'",
                       (since,))
    users = {r["user_id"] for r in rows}
    sent = [r for r in rows if r["status"] == "sent"]
    with_fb = [r for r in sent if r["feedback"]]
    unsub = sum(r["feedback"] == "unsubscribed" for r in sent)
    weeks = days / 7
    return {
        "window_days": days,
        "alerts_sent": len(sent),
        "alerts_per_user_per_week": round(len(sent) / max(len(users), 1) / weeks, 2),
        "suppressed_by_reason": {k: sum(1 for r in rows if r["status"] == "suppressed" and r["reason"] == k)
                                 for k in {r["reason"] for r in rows if r["status"] == "suppressed"}},
        "useful_rate": round(sum(r["feedback"] == "useful" for r in with_fb) / len(with_fb), 3) if with_fb else None,
        "unsubscribe_after_alert_rate": round(unsub / len(sent), 3) if sent else None,
        # Alert-fatigue index: high when people get many alerts AND find them not useful / unsubscribe.
        "fatigue_index": round((len(sent) / max(len(users), 1) / weeks) *
                               (1 - (sum(r["feedback"] == "useful" for r in with_fb) / len(with_fb) if with_fb else 0.5)) +
                               (unsub / len(sent) if sent else 0), 3),
    }


def bands() -> list[str]:
    return BAND_ORDER


def describe_ward(ward_id: str) -> str:
    return ward_name(ward_id)
