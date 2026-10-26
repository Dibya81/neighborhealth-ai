"""Your data, your call: export everything we hold about a person, or delete it.

Deletion removes the person's account, reports (and the photo files), saved places, alerts, consents,
assistant questions and usage events. Things other people or the health team depend on are kept but
cut loose from the person:
  * tasks created from their reports stay (the work still has to be done) but lose the link to the report;
  * other residents' reports that were merged into theirs as duplicates stay, unlinked;
  * audit-trail entries by an official keep their place in history, attributed to "deleted-user".
Aggregate counts (e.g. how many reports a ward had) are derived from rows and so shrink accordingly;
nothing here keeps a person-level copy.
"""
from __future__ import annotations

from app import db
from app.settings import get_settings

DELETED = "deleted-user"


def _ids(table: str, user_col: str, user_id: str) -> list[str]:
    return [r["id"] for r in db.fetchall(f"SELECT id FROM {table} WHERE {user_col} = ?", (user_id,))]


def export_user_data(user_id: str) -> dict:
    """Everything we hold about the user, as plain JSON (no password hash, no other people's data)."""
    u = db.fetchone("SELECT id, email, phone, name, role, language, cohort, created_at FROM users WHERE id = ?", (user_id,))
    return {
        "profile": u,
        "reports": db.fetchall("SELECT id, lat, lon, ward_id, category, description, photo_path, status, created_at "
                               "FROM reports WHERE user_id = ?", (user_id,)),
        "subscriptions": db.fetchall("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)),
        "alerts": db.fetchall("SELECT id, ward_id, band, horizon, channel, status, created_at, sent_at, feedback "
                              "FROM alerts WHERE user_id = ? AND status != 'marker'", (user_id,)),
        "consents": db.fetchall("SELECT kind, version, granted, at FROM consents WHERE user_id = ?", (user_id,)),
        "assistant_questions": db.fetchall("SELECT question, answer, language, created_at FROM chat_logs "
                                           "WHERE user_id = ?", (user_id,)),
        "events": db.fetchall("SELECT name, props, at FROM events WHERE user_id = ?", (user_id,)),
    }


def delete_user_data(user_id: str) -> dict:
    """Delete the user and their data. Returns how many rows were removed per table (for the receipt)."""
    removed: dict[str, int] = {}
    report_ids = _ids("reports", "user_id", user_id)

    # Photo files first: a failed row delete must never leave a photo of a deleted person on disk.
    photos = [r["photo_path"] for r in db.fetchall("SELECT photo_path FROM reports WHERE user_id = ?", (user_id,))]
    folder = get_settings().upload_dir / "reports"
    n_files = 0
    for name in photos:
        if name and (folder / name).is_file():
            (folder / name).unlink()
            n_files += 1
    removed["photo_files"] = n_files

    for rid in report_ids:                                   # cut links, don't destroy other people's records
        db.execute("UPDATE tasks SET report_id = NULL WHERE report_id = ?", (rid,))
        db.execute("UPDATE reports SET duplicate_of = NULL WHERE duplicate_of = ?", (rid,))
    # Audit trail attribution (officials) stays, but not the identity.
    db.execute("UPDATE tasks SET created_by = ? WHERE created_by = ?", (DELETED, user_id))
    db.execute("UPDATE task_events SET actor = ? WHERE actor = ?", (DELETED, user_id))
    db.execute("UPDATE reports SET reviewed_by = ? WHERE reviewed_by = ?", (DELETED, user_id))

    for table in ("alerts", "subscriptions", "consents", "events", "chat_logs", "reports"):
        removed[table] = db.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,)) or 0
    removed["users"] = db.execute("DELETE FROM users WHERE id = ?", (user_id,)) or 0
    return removed
