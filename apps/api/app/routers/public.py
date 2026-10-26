"""Public, read-only endpoints: city config, forecast, ward estimates, model transparency."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app import db
from app.forecast_store import get_bundle, ward_estimate
from app.geo import ward_at, ward_name
from app.services.assistant.explain import explain_ward
from pipeline.config import load_city

router = APIRouter(prefix="/v2", tags=["public"])


def _bundle() -> dict:
    b = get_bundle()
    if not b:
        raise HTTPException(503, "No forecast has been published yet. Run: python -m ml weekly")
    return b


@router.get("/city")
def city():
    cfg = load_city()
    return {"city": cfg["city"], "languages": cfg["languages"], "bbox": cfg["geography"]["bbox"],
            "ward_id_key": cfg["geography"]["ward_id_key"], "ward_name_key": cfg["geography"]["ward_name_key"],
            "helplines": cfg["assistant"]["helplines"]}


@router.get("/forecast")
def forecast():
    b = _bundle()
    return {k: b[k] for k in ("generated_at", "city", "target", "model", "origin_week", "population_est",
                              "bands_per_100k", "history", "forecast", "drivers", "disclaimer") if k in b}


@router.get("/wards/risk")
def wards_risk(horizon: int = Query(1, ge=1, le=4)):
    b = _bundle()
    rows = b.get("wards", {}).get(str(horizon))
    if not isinstance(rows, list):
        raise HTTPException(503, "Ward estimates unavailable")
    keep = ("ward_id", "ward_name", "band", "rate_per_100k", "rate_lo80", "rate_hi80", "expected_cases",
            "cases_lo80", "cases_hi80", "p_high", "uncertainty", "population_est")
    return {"horizon": horizon, "week_end": next(f["week_end"] for f in b["forecast"] if f["horizon"] == horizon),
            "bands_per_100k": b.get("bands_per_100k"), "wards": [{k: w.get(k) for k in keep} for w in rows]}


@router.get("/wards/{ward_id}")
def ward_detail(ward_id: str):
    b = _bundle()
    per_h = []
    for f in b["forecast"]:
        est = ward_estimate(ward_id, f["horizon"])
        if est:
            per_h.append({"horizon": f["horizon"], "week_end": f["week_end"], **{k: est[k] for k in (
                "band", "rate_per_100k", "rate_lo80", "rate_hi80", "expected_cases", "cases_lo80", "cases_hi80",
                "p_high", "uncertainty")}})
    if not per_h:
        raise HTTPException(404, "Unknown ward")
    rep = db.fetchone("SELECT COUNT(*) AS n FROM reports WHERE ward_id = ? AND status = 'verified'", (ward_id,))
    open_tasks = db.fetchone("SELECT COUNT(*) AS n FROM tasks WHERE ward_id = ? AND status NOT IN ('inspected','cleared','closed')",
                             (ward_id,))
    est1 = ward_estimate(ward_id, 1)
    return {"ward_id": ward_id, "ward_name": ward_name(ward_id), "population_est": est1["population_est"],
            "relative_risk": est1.get("relative_risk"), "horizons": per_h, "verified_reports": rep["n"] if rep else 0,
            "open_tasks": open_tasks["n"] if open_tasks else 0, "drivers": b.get("drivers"),
            "disclaimer": b.get("disclaimer")}


@router.get("/wards/{ward_id}/explain")
def ward_explain(ward_id: str, horizon: int = Query(1, ge=1, le=4), lang: str = Query("en", pattern="^(en|kn|hi)$")):
    out = explain_ward(ward_id, horizon, lang)
    if not out.get("available"):
        raise HTTPException(404, "No estimate for this ward")
    db.insert("chat_logs", {"id": db.new_id(), "kind": "ward_explanation", "question": ward_id, "answer": out["text"],
                            "language": lang, "grounded": int(not out["verification_problems"]), "created_at": db.now()})
    return out


@router.get("/locate")
def locate(lat: float, lon: float):
    wid = ward_at(lat, lon)
    return {"ward_id": wid, "ward_name": ward_name(wid) if wid else None}


@router.get("/model")
def model_info():
    b = _bundle()
    return {"model": b.get("model"), "backtest": b.get("backtest"), "drift": b.get("drift"),
            "generated_at": b.get("generated_at"), "origin_week": b.get("origin_week")}
