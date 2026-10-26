from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app import db
from app.ratelimit import limit
from app.security import optional_user, require_role
from app.services import clinics
from app.services.assistant.assistant import answer
from app.services.pilot import metrics, track

router = APIRouter(prefix="/v2", tags=["assistant"])


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=800)
    language: str = Field("en", pattern="^(en|kn|hi)$")
    lat: float | None = None
    lon: float | None = None


@router.post("/assistant/ask", dependencies=[Depends(limit("ask", 20, 60))])
def ask(body: AskIn, user: dict | None = Depends(optional_user)):
    res = answer(body.question, body.language, user["id"] if user else None)
    if res.get("urgent") and body.lat is not None and body.lon is not None:
        res["nearby"] = clinics.nearest(body.lat, body.lon, n=3, kind="hospital")
    return res


@router.get("/clinics/nearby")
def nearby(lat: float, lon: float, n: int = Query(5, ge=1, le=20), kind: str | None = None):
    items = clinics.nearest(lat, lon, n, kind)
    return {"clinics": items, "attribution": "© OpenStreetMap contributors (ODbL). Call ahead to confirm timings."}


class EventIn(BaseModel):
    name: str = Field(max_length=40)
    props: dict | None = None
    session_id: str | None = Field(None, max_length=64)


@router.post("/events", dependencies=[Depends(limit("events", 120, 60))])
def event(body: EventIn, user: dict | None = Depends(optional_user)):
    return {"ok": track(body.name, body.props, user["id"] if user else None, body.session_id)}


@router.get("/pilot/metrics")
def pilot_metrics(days: int = 28, cohort: str | None = None, user: dict = Depends(require_role("official", "admin"))):
    return metrics(days, cohort)


@router.get("/assistant/quality")
def assistant_quality(user: dict = Depends(require_role("official", "admin"))):
    rows = db.fetchall("SELECT kind, grounded, refused FROM chat_logs")
    q = [r for r in rows if r["kind"] == "question"]
    e = [r for r in rows if r["kind"] == "ward_explanation"]
    if not rows:
        raise HTTPException(404, "No assistant usage yet")
    return {"questions": len(q), "grounded_rate": round(sum(r["grounded"] or 0 for r in q) / len(q), 3) if q else None,
            "diagnosis_refusals": sum(r["refused"] or 0 for r in q), "explanations": len(e),
            "explanations_verified_rate": round(sum(r["grounded"] or 0 for r in e) / len(e), 3) if e else None}
