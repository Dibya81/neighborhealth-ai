"""Step 8, real users: consent records, privacy-preserving product analytics and pilot metrics.

Events never contain personal data: only an event name, a few whitelisted properties, the user id
(if signed in) and a random session id. Pilot metrics can be filtered by cohort (e.g. one RWA).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import db

CONSENT_VERSION = "2026-10"
ALLOWED_EVENTS = {
    "page_view", "ward_opened", "search", "report_started", "report_submitted", "subscription_created",
    "alert_opened", "assistant_question", "citation_opened", "share_clicked", "pwa_installed", "onboarding_done",
}
ALLOWED_PROPS = {"page", "ward_id", "horizon", "language", "source", "channel", "step"}


def record_consent(user_id: str, kind: str, granted: bool) -> None:
    db.insert("consents", {"id": db.new_id(), "user_id": user_id, "kind": kind, "version": CONSENT_VERSION,
                           "granted": int(granted), "at": db.now()})


def track(name: str, props: dict | None, user_id: str | None, session_id: str | None) -> bool:
    if name not in ALLOWED_EVENTS:
        return False
    clean = {k: str(v)[:64] for k, v in (props or {}).items() if k in ALLOWED_PROPS}
    db.insert("events", {"id": db.new_id(), "user_id": user_id, "session_id": (session_id or "")[:64],
                         "name": name, "props": clean, "at": db.now()})
    return True


def metrics(days: int = 28, cohort: str | None = None) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cohort_sql, cp = ("AND u.cohort = ?", [cohort]) if cohort else ("", [])

    def one(q: str, params: list) -> int:
        r = db.fetchone(q, params)
        return int(list(r.values())[0] or 0) if r else 0

    users = one(f"SELECT COUNT(*) FROM users u WHERE u.role = 'citizen' {cohort_sql}", cp)
    subscribed = one(f"SELECT COUNT(DISTINCT s.user_id) FROM subscriptions s JOIN users u ON u.id = s.user_id "
                     f"WHERE s.active = 1 {cohort_sql}", cp)
    reports = one(f"SELECT COUNT(*) FROM reports r LEFT JOIN users u ON u.id = r.user_id WHERE r.created_at >= ? {cohort_sql}",
                  [since, *cp])
    verified = one(f"SELECT COUNT(*) FROM reports r LEFT JOIN users u ON u.id = r.user_id WHERE r.created_at >= ? "
                   f"AND r.status = 'verified' {cohort_sql}", [since, *cp])
    wau = one(f"SELECT COUNT(DISTINCT e.user_id) FROM events e LEFT JOIN users u ON u.id = e.user_id WHERE e.at >= ? "
              f"AND e.user_id IS NOT NULL {cohort_sql}", [(datetime.now(timezone.utc) - timedelta(days=7)).isoformat(), *cp])
    sessions = one("SELECT COUNT(DISTINCT session_id) FROM events WHERE at >= ?", [since])
    tasks_closed = one("SELECT COUNT(*) FROM tasks WHERE completed_at >= ?", [since])
    cohorts = db.fetchall("SELECT cohort, COUNT(*) AS users FROM users WHERE cohort IS NOT NULL GROUP BY cohort")
    return {"window_days": days, "cohort": cohort, "registered_citizens": users, "subscribed_users": subscribed,
            "reports": reports, "verified_reports": verified,
            "verification_rate": round(verified / reports, 3) if reports else None,
            "weekly_active_users": wau, "sessions": sessions, "tasks_completed": tasks_closed, "cohorts": cohorts}
