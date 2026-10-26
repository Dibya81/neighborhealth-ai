"""Deleting a person's data must remove theirs and nothing else."""
import json

from app import db
from app.services import privacy
from app.settings import get_settings


def _user(email):
    uid = db.new_id()
    db.insert("users", {"id": uid, "email": email, "password_hash": "x", "role": "citizen", "language": "en",
                        "created_at": db.now()})
    return uid


def _report(uid, photo, duplicate_of=None):
    rid = db.new_id()
    db.insert("reports", {"id": rid, "user_id": uid, "lat": 12.97, "lon": 77.59, "ward_id": "1", "category": "tyre",
                          "photo_path": photo, "status": "pending", "duplicate_of": duplicate_of, "created_at": db.now()})
    return rid


def test_delete_removes_only_that_persons_data_and_keeps_work_in_progress():
    db.migrate()
    tag = db.new_id()[:8]                      # the test DB persists between runs; keep emails unique
    a, b = _user(f"a-{tag}@example.com"), _user(f"b-{tag}@example.com")
    folder = get_settings().upload_dir / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "a-photo.jpg").write_bytes(b"x")
    (folder / "b-photo.jpg").write_bytes(b"x")
    ra, rb = _report(a, "a-photo.jpg"), _report(b, "b-photo.jpg", duplicate_of=None)
    rb_dup = _report(b, "b-photo.jpg", duplicate_of=ra)             # B's report was merged into A's
    task = db.new_id()
    db.insert("tasks", {"id": task, "report_id": ra, "ward_id": "1", "lat": 12.97, "lon": 77.59, "status": "open",
                        "created_by": a, "created_at": db.now(), "updated_at": db.now()})
    for uid in (a, b):
        db.insert("consents", {"id": db.new_id(), "user_id": uid, "kind": "terms", "version": "1", "granted": 1, "at": db.now()})
        db.insert("chat_logs", {"id": db.new_id(), "user_id": uid, "kind": "question", "question": "q", "answer": "a",
                                "citations": "[]", "language": "en", "created_at": db.now()})
        db.insert("events", {"id": db.new_id(), "user_id": uid, "name": "open", "at": db.now()})

    exported = privacy.export_user_data(a)
    assert exported["profile"]["email"] == f"a-{tag}@example.com" and "password_hash" not in json.dumps(exported)
    assert len(exported["reports"]) == 1 and len(exported["consents"]) == 1

    removed = privacy.delete_user_data(a)

    assert removed["users"] == 1 and removed["reports"] == 1 and removed["photo_files"] == 1
    assert not (folder / "a-photo.jpg").exists()                       # the photo is gone from disk
    assert db.fetchone("SELECT id FROM users WHERE id = ?", (a,)) is None
    for table in ("reports", "consents", "chat_logs", "events"):
        assert db.fetchone(f"SELECT 1 FROM {table} WHERE user_id = ?", (a,)) is None
    # B is untouched
    assert db.fetchone("SELECT id FROM users WHERE id = ?", (b,)) is not None
    assert db.fetchone("SELECT 1 FROM consents WHERE user_id = ?", (b,)) and (folder / "b-photo.jpg").exists()
    assert db.fetchone("SELECT duplicate_of FROM reports WHERE id = ?", (rb_dup,))["duplicate_of"] is None   # unlinked, kept
    # the field task survives, no longer pointing at the deleted report or person
    t = db.fetchone("SELECT report_id, created_by FROM tasks WHERE id = ?", (task,))
    assert t["report_id"] is None and t["created_by"] == privacy.DELETED
    (folder / "b-photo.jpg").unlink()
