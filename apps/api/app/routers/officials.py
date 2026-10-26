"""Health officials' tools: overview, review queue, tasks, route planning. Requires role official/admin."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app import db
from app.forecast_store import get_bundle
from app.security import require_role
from app.services import tasks as task_svc
from app.services.alerts.engine import fatigue_metrics
from app.services.hotspots import detect_hotspots
from app.services.reports import ReportRejected, review, trust_score
from app.services.routing import Stop, optimise
from pipeline.config import load_city

router = APIRouter(prefix="/v2/officials", tags=["officials"])
official = require_role("official", "admin")


@router.get("/overview")
def overview(user: dict = Depends(official)):
    b = get_bundle() or {}
    wards = b.get("wards", {}).get("1") if isinstance(b.get("wards", {}).get("1"), list) else []
    top = sorted(wards, key=lambda w: -w["rate_per_100k"])[:10]
    pending = db.fetchone("SELECT COUNT(*) AS n FROM reports WHERE status = 'pending'")["n"]
    return {"forecast": b.get("forecast"), "origin_week": b.get("origin_week"), "drift": (b.get("drift") or {}).get("overall"),
            "top_wards": [{k: w[k] for k in ("ward_id", "ward_name", "band", "rate_per_100k", "rate_lo80", "rate_hi80",
                                            "p_high", "uncertainty")} for w in top],
            "hotspots": detect_hotspots()[:10], "review_queue": pending, "tasks": task_svc.stats(),
            "alerts": fatigue_metrics()}


@router.get("/queue")
def queue(limit_: int = Query(50, alias="limit", ge=1, le=200), user: dict = Depends(official)):
    rows = db.fetchall("SELECT * FROM reports WHERE status = 'pending' ORDER BY "
                       "CASE vision_label WHEN 'likely_breeding_site' THEN 0 WHEN 'uncertain' THEN 1 ELSE 2 END, created_at "
                       "LIMIT ?", (limit_,))
    trust_cache: dict = {}
    out = []
    for r in rows:
        uid = r["user_id"]
        if uid not in trust_cache:
            trust_cache[uid] = trust_score(uid)
        out.append({**{k: r[k] for k in ("id", "lat", "lon", "ward_id", "category", "description", "vision_label",
                                         "vision_score", "created_at")},
                    "flags": db.loads(r["flags"], []), "reporter_trust": trust_cache[uid],
                    "photo_url": f"/v2/reports/{r['id']}/photo"})
    return {"reports": out}


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(verified|rejected|spam)$")
    create_task: bool = True


@router.post("/reports/{report_id}/review")
def review_report(report_id: str, body: ReviewIn, user: dict = Depends(official)):
    try:
        return review(report_id, user, body.decision, body.create_task)
    except ReportRejected as e:
        raise HTTPException(422, str(e))


class TaskIn(BaseModel):
    lat: float
    lon: float
    ward_id: str | None = None
    kind: str = Field("inspection", pattern="^(inspection|fogging|source_reduction)$")
    priority: int = Field(2, ge=1, le=3)
    notes: str | None = Field(None, max_length=500)


@router.get("/tasks")
def list_tasks(status: str | None = None, ward_id: str | None = None, user: dict = Depends(official)):
    q, p = "SELECT * FROM tasks WHERE 1=1", []
    if status:
        q += " AND status = ?"
        p.append(status)
    if ward_id:
        q += " AND ward_id = ?"
        p.append(ward_id)
    return {"tasks": db.fetchall(q + " ORDER BY priority, created_at DESC LIMIT 500", p), "stats": task_svc.stats()}


@router.post("/tasks")
def new_task(body: TaskIn, user: dict = Depends(official)):
    from app.geo import ward_at
    return task_svc.create_task(body.lat, body.lon, body.ward_id or ward_at(body.lat, body.lon), body.kind,
                                body.priority, notes=body.notes, actor=user["id"])


class TransitionIn(BaseModel):
    status: str
    note: str | None = Field(None, max_length=500)
    team: str | None = Field(None, max_length=40)


@router.post("/tasks/{task_id}/transition")
def move_task(task_id: str, body: TransitionIn, user: dict = Depends(official)):
    try:
        return task_svc.transition(task_id, body.status, user["id"], body.note, body.team)
    except task_svc.TaskError as e:
        raise HTTPException(422, str(e))


@router.get("/tasks/{task_id}/events")
def task_events(task_id: str, user: dict = Depends(official)):
    return {"events": db.fetchall("SELECT * FROM task_events WHERE task_id = ? ORDER BY at", (task_id,))}


class RouteIn(BaseModel):
    depot_lat: float | None = None
    depot_lon: float | None = None
    task_ids: list[str] | None = None      # default: all open tasks
    teams: int = Field(1, ge=1, le=10)
    shift_minutes: int | None = Field(None, ge=30, le=720)
    assign: bool = True


@router.post("/routes/optimize")
def plan_route(body: RouteIn, user: dict = Depends(official)):
    city = load_city()["city"]
    depot = (body.depot_lat or city["lat"], body.depot_lon or city["lon"])
    if body.task_ids:
        marks = ",".join("?" for _ in body.task_ids)
        rows = db.fetchall(f"SELECT * FROM tasks WHERE id IN ({marks})", body.task_ids)
    else:
        rows = db.fetchall("SELECT * FROM tasks WHERE status IN ('open', 'assigned') ORDER BY created_at LIMIT 200")
    if not rows:
        raise HTTPException(422, "No open tasks to route")
    stops = [Stop(r["id"], r["lat"], r["lon"], r["priority"], label=f"{r['kind']} · ward {r['ward_id']}") for r in rows]
    plan = optimise(depot, stops, body.teams, body.shift_minutes)
    rid = db.new_id()
    db.insert("routes", {"id": rid, "created_by": user["id"], "team": None, "plan": plan, "created_at": db.now()})
    if body.assign:
        for route in plan["routes"]:
            for s in route["stops"]:
                db.update("tasks", s["stop_id"], {"route_id": rid, "team": f"Team {route['team']}",
                                                  "status": "assigned", "updated_at": db.now()})
    return {"route_id": rid, **plan}


@router.get("/routes/{route_id}")
def get_route(route_id: str, user: dict = Depends(official)):
    r = db.fetchone("SELECT * FROM routes WHERE id = ?", (route_id,))
    if not r:
        raise HTTPException(404, "Not found")
    return {"route_id": r["id"], "created_at": r["created_at"], **db.loads(r["plan"], {})}
