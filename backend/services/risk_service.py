"""
Risk Service
=============
Orchestrates the full prediction pipeline.
Called by daily_refresh.py and the admin trigger endpoint.
"""

from datetime import date
from utils.logger import get_logger

logger = get_logger("ML")
cron_logger = get_logger("CRON")


def run_prediction_pipeline() -> dict:
    """
    Full pipeline: data → features → inference → DB write.

    Steps:
        1. Fetch all ward IDs from DB
        2. Get weather features (cached or fresh from OWM)
        3. Get report counts per ward (last 7 days)
        4. Get historical case data per ward
        5. Get ward metadata (population density)
        6. Build 198×9 feature matrix
        7. Run XGBoost batch inference
        8. Write 198 rows to ward_risk_scores
        9. Return summary stats

    Returns:
        {"wards_processed": 198, "high_risk": N, "medium_risk": N,
         "low_risk": N, "score_date": "YYYY-MM-DD", "model_version": "..."}
    """
    from db.wards import get_all_wards
    from db.reports import get_report_counts_per_ward
    from db.risk_scores import insert_risk_scores_batch
    from services.weather_service import get_weather_features_for_pipeline
    from ml.features import (
        build_feature_matrix,
        get_historical_scores_from_db,
        get_ward_metadata_from_db,
    )
    from ml.predictor import predict_risk_scores, get_model_version
    from config.diseases import DISEASES
    from ml.rule_based import compute_rule_based_score, build_rule_based_ward_scores

    cron_logger.info("Daily refresh pipeline started")
    score_date = date.today().isoformat()

    # Step 1: Ward IDs
    wards = get_all_wards()
    ward_ids = [w["id"] for w in wards]
    logger.info("Step 1: %d wards loaded", len(ward_ids))

    # Step 2: Weather features
    weather_features = get_weather_features_for_pipeline()
    logger.info(
        "Step 2: Weather — rain7d=%.1fmm temp=%.1f°C hum=%.1f%%",
        weather_features["rainfall_7d"],
        weather_features["temp_avg"],
        weather_features["humidity_avg"],
    )

    # Step 3: Community report counts
    report_counts = get_report_counts_per_ward(days=7)
    logger.info("Step 3: Report counts for %d wards", len(report_counts))

    # Step 4: Historical case data
    historical_scores = get_historical_scores_from_db(ward_ids)
    logger.info("Step 4: Historical scores loaded")

    # Step 5: Ward metadata
    ward_metadata = get_ward_metadata_from_db()
    logger.info("Step 5: Ward metadata loaded")

    # Step 6: Feature matrix
    feature_df = build_feature_matrix(
        ward_ids=ward_ids,
        weather_features=weather_features,
        report_counts=report_counts,
        historical_scores=historical_scores,
        ward_metadata=ward_metadata,
    )
    logger.info("Step 6: Feature matrix built — shape %s", feature_df.shape)

    # Step 7 & 8: Inference and DB insert per disease
    model_version = get_model_version()
    rows_to_insert = []

    for disease_id, disease_cfg in DISEASES.items():
        # Predictor now handles all routing (ML vs Rule-based + Malaria hybrid)
        scores_df = predict_risk_scores(feature_df, disease_id, ward_metadata)
        logger.info("Inference complete for disease '%s' (version: %s)", disease_id, model_version)

        for _, row in scores_df.iterrows():
            wid = row["ward_id"]
            rows_to_insert.append({
                "ward_id": wid,
                "disease_id": disease_id,
                "score_date": score_date,
                "risk_score": float(row["risk_score"]),
                "risk_level": row["risk_level"],
                "ai_reason": row["ai_reason"], # Stored as JSON/list
                "rainfall_7d": weather_features["rainfall_7d"],
                "temp_avg": weather_features["temp_avg"],
                "humidity_avg": weather_features["humidity_avg"],
                "dengue_cases": int(historical_scores.get(wid, {}).get("dengue_cases_30d", 0)) if disease_id == "dengue" else 0,
                "report_count": int(report_counts.get(wid, 0)),
                "model_version": model_version,
            })

    insert_risk_scores_batch(rows_to_insert)
    logger.info("Step 8: %d rows written to ward_risk_scores across all diseases", len(rows_to_insert))

    # Step 9: Summary
    high = sum(1 for r in rows_to_insert if r["risk_level"] == "high")
    medium = sum(1 for r in rows_to_insert if r["risk_level"] == "medium")
    low = sum(1 for r in rows_to_insert if r["risk_level"] == "low")

    summary = {
        "wards_processed": len(rows_to_insert),
        "high_risk": high,
        "medium_risk": medium,
        "low_risk": low,
        "score_date": score_date,
        "model_version": model_version,
        "rainfall_7d_mm": weather_features["rainfall_7d"],
    }

    logger.info(
        f"Generated scores for {len(rows_to_insert)} ward/disease pairs | avg_rain={weather_features['rainfall_7d']:.1f}mm"
    )
    cron_logger.info(f"Pipeline complete | low={low} med={medium} high={high}")
    return summary
