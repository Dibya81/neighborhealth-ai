from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from models.risk import RiskAllResponse, RiskScoreDetail, RiskHistoryResponse, RiskScoreSummary, RiskSignals, RiskHistoryEntry
from db.risk_scores import get_latest_scores_all_wards, get_latest_score_for_ward, get_score_history_for_ward
from db.wards import get_ward_by_id
from utils.cache import cache
from utils.logger import get_logger
from api.deps import verify_admin_key
from services.risk_service import run_prediction_pipeline

router = APIRouter()
logger = get_logger(__name__)

CACHE_KEY_ALL = "risk:all"
CACHE_TTL = 3600  # 1 hour


@router.get("/risk/all", response_model=RiskAllResponse, tags=["risk"])
async def get_all_risk_scores(disease: str = "dengue"):
    """
    Returns the latest risk scores for all 198 BBMP wards for a specific disease.
    """
    from db.client import get_supabase
    
    # Cache key includes disease to prevent cross-data leakage
    cache_key = f"{CACHE_KEY_ALL}:{disease}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    sb = get_supabase()
    
    # Step 1: Find the latest available date for this disease
    latest_res = sb.table("ward_risk_scores") \
                   .select("score_date") \
                   .eq("disease_id", disease) \
                   .order("score_date", desc=True) \
                   .limit(1) \
                   .execute()
                   
    if not latest_res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No risk scores available for disease: {disease}",
        )
        
    latest_date = latest_res.data[0]["score_date"]

    # Step 2: Fetch all scores for that date
    scores_res = sb.table("ward_risk_scores") \
                   .select("ward_id, risk_score, risk_level, score_date") \
                   .eq("disease_id", disease) \
                   .eq("score_date", latest_date) \
                   .execute()
    
    scores = scores_res.data

    response = RiskAllResponse(
        generated_at=datetime.utcnow().isoformat(),
        total_wards=len(scores),
        wards=[
            RiskScoreSummary(
                ward_id=s["ward_id"],
                risk_score=s["risk_score"],
                risk_level=s["risk_level"],
                disease=disease,
                score_date=s.get("score_date"),
            )
            for s in scores
        ],
    )
    cache.set(cache_key, response, ttl_seconds=CACHE_TTL)
    return response

@router.get("/risk/all/{disease_id}", response_model=RiskAllResponse, tags=["risk"])
async def get_risk_for_disease_legacy(disease_id: str):
    """Legacy path param support; delegates to query param handler."""
    return await get_all_risk_scores(disease=disease_id)


@router.get("/alerts/today", tags=["alerts"])
async def get_today_alerts():
    """Returns active health alerts fetched by Groq this morning."""
    from db.client import get_supabase
    score_date = datetime.utcnow().date().isoformat()
    sb = get_supabase()
    
    response = sb.table("active_alerts") \
                 .select("*") \
                 .eq("alert_date", score_date) \
                 .execute()
                 
    if not response.data:
        # Fallback to most recent alert
        latest_res = sb.table("active_alerts") \
                       .select("*") \
                       .order("alert_date", desc=True) \
                       .limit(1) \
                       .execute()
        return {"alerts": latest_res.data}

    return {"alerts": response.data}

@router.get("/risk/ward/{ward_id}", response_model=RiskScoreDetail, tags=["risk"])
@router.get("/risk/{ward_id}", response_model=RiskScoreDetail, tags=["risk"])
async def get_ward_risk(ward_id: str, disease: str = "dengue"):
    """
    Returns the full risk breakdown for a single ward.
    Includes contributing signals and 5-day trend for the detail panel.
    """
    from db.client import get_supabase
    sb = get_supabase()
    
    # Ensure latest only: order by score_date desc limit 1
    res = sb.table("ward_risk_scores") \
            .select("*") \
            .eq("ward_id", ward_id) \
            .eq("disease_id", disease) \
            .order("score_date", desc=True) \
            .limit(1) \
            .execute()
            
    score = res.data[0] if res.data else None

    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No risk data found for ward {ward_id} and disease {disease}.",
        )

    ward = get_ward_by_id(ward_id)
    ward_name = ward["name"] if ward else None

    # Build trend from history (last 5 days)
    h_res = sb.table("ward_risk_scores") \
              .select("risk_score, score_date") \
              .eq("ward_id", ward_id) \
              .eq("disease_id", disease) \
              .order("score_date", desc=True) \
              .limit(5) \
              .execute()
    history = h_res.data
    trend = [h["risk_score"] for h in history]
    trend.reverse() # chronological
    trend_direction = _compute_trend_direction(trend)

    # AI reason column (list[str]) -> reasons
    reasons = score.get("ai_reason")
    if isinstance(reasons, str):
        try:
            import json
            reasons = json.loads(reasons)
        except:
            reasons = [reasons]

    return RiskScoreDetail(
        ward_id=ward_id,
        ward_name=ward_name,
        risk_score=score["risk_score"],
        risk_level=score["risk_level"],
        disease=disease,
        score_date=str(score.get("score_date", "")),
        signals=RiskSignals(
            rainfall_7d=score.get("rainfall_7d"),
            temp_avg=score.get("temp_avg"),
            humidity_avg=score.get("humidity_avg"),
            dengue_cases=score.get("dengue_cases"),
            report_count=score.get("report_count"),
        ),
        reasons=reasons,
        trend=trend,
        trend_direction=trend_direction,
        model_version=score.get("model_version"),
    )


@router.get("/risk/{ward_id}/history", response_model=RiskHistoryResponse, tags=["risk"])
async def get_ward_history(ward_id: str, days: int = 30, disease: str = "dengue"):
    """
    Returns last N days of daily risk scores for a ward.
    Powers the sparkline trend chart in the ward detail panel.
    """
    from db.client import get_supabase
    sb = get_supabase()
    
    if days > 90:
        days = 90
        
    h_res = sb.table("ward_risk_scores").select("*").eq("ward_id", ward_id).eq("disease_id", disease).order("score_date", desc=True).limit(days).execute()
    history = h_res.data
    
    return RiskHistoryResponse(
        ward_id=ward_id,
        history=[
            RiskHistoryEntry(
                date=str(h["score_date"]),
                risk_score=h["risk_score"],
                risk_level=h["risk_level"],
            )
            for h in history
        ],
    )


@router.post("/admin/trigger-refresh", tags=["admin"])
async def trigger_refresh(_: None = Depends(verify_admin_key)):
    """
    Manually triggers the full prediction pipeline.
    Protected by x-admin-key header.
    Called by GitHub Actions cron AND during live demos.
    """
    logger.info("Manual pipeline trigger via admin endpoint")
    try:
        summary = run_prediction_pipeline()
        # Invalidate the all-wards cache so next map load gets fresh data
        cache.delete(CACHE_KEY_ALL)
        return {"status": "completed", "summary": summary}
    except Exception as e:
        logger.error("Pipeline failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")


@router.get("/admin/stats", tags=["admin"])
async def get_admin_stats(_: None = Depends(verify_admin_key)):
    """Returns aggregate platform statistics for the admin dashboard."""
    from db.client import get_supabase
    from db.risk_scores import get_last_pipeline_run

    sb = get_supabase()
    sub_count = sb.table("subscriptions").select("id", count="exact").eq("active", True).execute()
    report_count = sb.table("breeding_reports").select("id", count="exact").execute()
    scores = get_latest_scores_all_wards()
    high_risk = sum(1 for s in scores if s["risk_level"] == "high")

    return {
        "total_subscribers": sub_count.count or 0,
        "total_reports": report_count.count or 0,
        "high_risk_wards": high_risk,
        "last_pipeline_run": get_last_pipeline_run(),
    }


def _compute_trend_direction(trend: list[float]) -> str:
    if len(trend) < 2:
        return "stable"
    recent_avg = sum(trend[-2:]) / 2
    earlier_avg = sum(trend[:2]) / 2
    diff = recent_avg - earlier_avg
    if diff > 5:
        return "rising"
    if diff < -5:
        return "falling"
    return "stable"

@router.post("/risk/travel", tags=["risk"])
async def travel_risk(payload: dict):
    """
    Accepts from_ward_id and to_ward_id.
    Returns risk profile for both wards + AI travel advisory.
    """
    from db.client import get_supabase
    from db.wards import get_ward_by_id
    
    from_ward = payload.get("from_ward_id")
    to_ward   = payload.get("to_ward_id")
    disease   = payload.get("disease", "dengue")
    user_health = payload.get("user_health_conditions", [])

    if not from_ward or not to_ward:
        raise HTTPException(status_code=400, detail="from_ward_id and to_ward_id required")

    sb = get_supabase()

    def _get_score(ward_id):
        res = (sb.table("ward_risk_scores")
               .select("ward_id, risk_score, risk_level, rainfall_7d, temp_avg, dengue_cases, report_count")
               .eq("ward_id", ward_id)
               .eq("disease_id", disease)
               .order("score_date", desc=True)
               .limit(1)
               .execute())
        return res.data[0] if res.data else None

    from_score = _get_score(from_ward)
    to_score   = _get_score(to_ward)
    from_name  = (get_ward_by_id(from_ward) or {}).get("name", f"Ward {from_ward}")
    to_name    = (get_ward_by_id(to_ward) or {}).get("name", f"Ward {to_ward}")

    # Build travel advisory via AI
    health_ctx = f"Traveler has: {', '.join(user_health)}. " if user_health else ""
    message = (
        f"{health_ctx}Analyze travel from {from_name} (risk {int(from_score['risk_score']) if from_score else '?'}/100) "
        f"to {to_name} (risk {int(to_score['risk_score']) if to_score else '?'}/100) for {disease}. "
        f"Give: 1) Overall travel safety, 2) Precautions for the destination, 3) Best time to travel. "
        f"Keep it to 3-4 sentences."
    )

    from services.chat_service import generate_ward_advisory
    advisory = generate_ward_advisory(
        ward_id=to_ward,
        user_message=message,
        language=payload.get("language", "en"),
        user_health_conditions=user_health,
    )

    return {
        "from": {"ward_id": from_ward, "name": from_name, "score": from_score},
        "to":   {"ward_id": to_ward,   "name": to_name,   "score": to_score},
        "disease": disease,
        "advisory": advisory["response"],
    }
