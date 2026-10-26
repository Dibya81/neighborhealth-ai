"""Field tasks for health officials, with a full audit trail (closing the loop: what was actually done)."""
from __future__ import annotations

from app import db

FLOW = {
    "open": {"assigned", "in_progress", "closed"},
    "assigned": {"in_progress", "open", "closed"},
    "in_progress": {"inspected", "cleared", "assigned"},
    "inspected": {"cleared", "closed", "in_progress"},
    "cleared": {"closed"},
    "closed": set(),
}
DONE = {"inspected", "cleared", "closed"}


class TaskError(Exception):
    pass


def create_task(lat: float, lon: float, ward_id: str | None, kind: str = "inspection", priority: int = 2,
                report_id: str | None = None, notes: str | None = None, actor: str | None = None) -> dict:
    t = {"id": db.new_id(), "report_id": report_id, "ward_id": ward_id, "lat": lat, "lon": lon, "kind": kind,
         "priority": int(priority), "status": "open", "notes": notes, "created_by": actor,
         "created_at": db.now(), "updated_at": db.now()}
    db.insert("tasks", t)
    db.insert("task_events", {"id": db.new_id(), "task_id": t["id"], "status": "open", "actor": actor,
                              "note": "created", "at": db.now()})
    return t


def transition(task_id: str, new_status: str, actor: str, note: str | None = None, team: str | None = None) -> dict:
    t = db.fetchone("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if not t:
        raise TaskError("task not found")
    if new_status not in FLOW.get(t["status"], set()):
        raise TaskError(f"cannot move from {t['status']} to {new_status}")
    changes = {"status": new_status, "updated_at": db.now()}
    if team:
        changes["team"] = team
    if new_status in DONE and not t["completed_at"]:
        changes["completed_at"] = db.now()
    db.update("tasks", task_id, changes)
    db.insert("task_events", {"id": db.new_id(), "task_id": task_id, "status": new_status, "actor": actor,
                              "note": note, "at": db.now()})
    if new_status == "cleared" and t["report_id"]:
        db.update("reports", t["report_id"], {"status": "verified"})
    return {**t, **changes}


def stats() -> dict:
    rows = db.fetchall("SELECT status, COUNT(*) AS n FROM tasks GROUP BY status")
    by = {r["status"]: int(r["n"]) for r in rows}
    done = db.fetchall("SELECT created_at, completed_at FROM tasks WHERE completed_at IS NOT NULL")
    from datetime import datetime
    hours = [(datetime.fromisoformat(d["completed_at"]) - datetime.fromisoformat(d["created_at"])).total_seconds() / 3600
             for d in done]
    hours.sort()
    return {"by_status": by, "open": sum(v for k, v in by.items() if k not in DONE),
            "completed": sum(v for k, v in by.items() if k in DONE),
            "median_hours_to_complete": round(hours[len(hours) // 2], 1) if hours else None}
