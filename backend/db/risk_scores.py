from __future__ import annotations
from datetime import date, timedelta
from typing import Optional
from db.client import get_supabase
from utils.logger import get_logger

logger = get_logger("DB")
# ... existing imports ...


def get_latest_scores_all_wards(disease: str = "dengue") -> list[dict]:
    """
    Returns today's risk score for every ward for a specific disease.
    """
    sb = get_supabase()
    
    # Get the single absolute latest date available for this disease
    latest_query = (
        sb.table("ward_risk_scores")
        .select("score_date")
        .eq("disease_id", disease)
        .order("score_date", desc=True)
        .limit(1)
        .execute()
    )
    
    if not latest_query.data:
        return []
        
    latest_date = latest_query.data[0]["score_date"]

    result = (
        sb.table("ward_risk_scores")
        .select("ward_id, risk_score, risk_level, score_date, disease_id")
        .eq("score_date", latest_date)
        .eq("disease_id", disease)
        .execute()
    )

    return result.data


def get_latest_score_for_ward(ward_id: str, disease: str = "dengue") -> Optional[dict]:
    """
    Returns the most recent risk score row for a specific ward and disease,
    including all contributing signal values and AI explanation.
    """
    sb = get_supabase()
    result = (
        sb.table("ward_risk_scores")
        .select(
            "ward_id, score_date, risk_score, risk_level, disease_id, "
            "rainfall_7d, temp_avg, humidity_avg, "
            "dengue_cases, report_count, model_version, ai_reason, created_at"
        )
        .eq("ward_id", ward_id)
        .eq("disease_id", disease)
        .order("score_date", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def get_score_history_for_ward(ward_id: str, disease: str = "dengue", days: int = 30) -> list[dict]:
    """
    Returns the last N days of daily risk scores for a ward and disease.
    """
    sb = get_supabase()
    since = (date.today() - timedelta(days=days)).isoformat()

    result = (
        sb.table("ward_risk_scores")
        .select("score_date, risk_score, risk_level")
        .eq("ward_id", ward_id)
        .eq("disease_id", disease)
        .gte("score_date", since)
        .order("score_date", desc=False)
        .execute()
    )
    return result.data


def insert_risk_scores_batch(scores: list[dict]) -> None:
    """
    Batch inserts 198 risk score rows.
    ON CONFLICT (ward_id, score_date) → DO NOTHING (idempotent, safe to re-run).
    """
    sb = get_supabase()
    try:
        logger.info(f"Insert risk scores ({len(scores)} rows)")
        sb.table("ward_risk_scores").upsert(
            scores, on_conflict="ward_id,score_date,disease_id", ignore_duplicates=True
        ).execute()
    except Exception as e:
        # Fallback: if 'ai_reason' column is missing, try without it
        if "ai_reason" in str(e) or "explanation" in str(e):
            logger.warning("DB column 'ai_reason' missing. Retrying insert without it.")
            stripped_scores = [{k: v for k, v in s.items() if k not in ["ai_reason", "explanation"]} for s in scores]
            sb.table("ward_risk_scores").upsert(
                stripped_scores, on_conflict="ward_id,score_date,disease_id", ignore_duplicates=True
            ).execute()
            logger.info("Inserted %d risk score rows (without explanations)", len(scores))
        else:
            logger.error("Failed to insert risk scores batch: %s", e)
            raise e



def get_last_pipeline_run() -> Optional[str]:
    """Returns the most recent score_date as an ISO string, or None."""
    sb = get_supabase()
    result = (
        sb.table("ward_risk_scores")
        .select("score_date")
        .order("score_date", desc=True)
        .limit(1)
        .execute()
    )
    if result.data:
        return result.data[0]["score_date"]
    return None
