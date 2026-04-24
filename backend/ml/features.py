from __future__ import annotations
import pandas as pd
import numpy as np
from datetime import date, timedelta
from utils.logger import get_logger

logger = get_logger(__name__)

# Must match train_model.py FEATURE_COLUMNS exactly
FEATURE_COLUMNS = [
    "rainfall_7d",
    "rainfall_lag14",
    "temp_avg",
    "humidity_avg",
    "dengue_cases_30d",
    "dengue_cases_prev_year",
    "report_count_7d",
    "month",
    "population_density",
]


def build_feature_matrix(
    ward_ids: list[str],
    weather_features: dict,
    report_counts: dict[str, int],
    historical_scores: dict[str, dict],
    ward_metadata: dict[str, dict],
) -> pd.DataFrame:
    current_month = date.today().month
    rows = []
    for ward_id in ward_ids:
        hist = historical_scores.get(ward_id, {})
        meta = ward_metadata.get(ward_id, {})
        row = {
            "ward_id":               ward_id,
            "rainfall_7d":           weather_features.get("rainfall_7d", 0.0),
            "rainfall_lag14":        weather_features.get("rainfall_lag14", 0.0),
            "temp_avg":              weather_features.get("temp_avg", 27.0),
            "humidity_avg":          weather_features.get("humidity_avg", 75.0),
            "dengue_cases_30d":      hist.get("dengue_cases_30d", 0),
            "dengue_cases_prev_year":hist.get("dengue_cases_prev_year", 0),
            "report_count_7d":       report_counts.get(ward_id, 0),
            "month":                 current_month,
            "population_density":    meta.get("population_density", 10000),
        }
        rows.append(row)

    df = pd.DataFrame(rows).set_index("ward_id")[FEATURE_COLUMNS]

    assert df.shape[0] == len(ward_ids)
    assert df.shape[1] == len(FEATURE_COLUMNS)
    assert not df.isnull().any().any(), "NaN in feature matrix"

    logger.info(
        "Feature matrix: %d×%d | month=%d rain7d=%.1fmm lag14=%.1fmm",
        df.shape[0], df.shape[1], current_month,
        weather_features.get("rainfall_7d", 0),
        weather_features.get("rainfall_lag14", 0),
    )
    return df


def get_historical_scores_from_db(ward_ids: list[str]) -> dict[str, dict]:
    from db.client import get_supabase
    sb  = get_supabase()
    tod = date.today()

    r30 = (
        sb.table("ward_risk_scores")
        .select("ward_id, dengue_cases")
        .eq("disease_id", "dengue")
        .gte("score_date", (tod - timedelta(days=30)).isoformat())
        .execute()
    )
    cases_30d: dict[str, int] = {}
    for row in r30.data:
        wid = row["ward_id"]
        cases_30d[wid] = cases_30d.get(wid, 0) + (row["dengue_cases"] or 0)

    r_prev = (
        sb.table("ward_risk_scores")
        .select("ward_id, dengue_cases")
        .eq("disease_id", "dengue")
        .gte("score_date", tod.replace(year=tod.year - 1, day=1).isoformat())
        .lte("score_date", tod.replace(year=tod.year - 1).isoformat())
        .execute()
    )
    cases_prev: dict[str, int] = {}
    for row in r_prev.data:
        wid = row["ward_id"]
        cases_prev[wid] = cases_prev.get(wid, 0) + (row["dengue_cases"] or 0)

    return {
        wid: {
            "dengue_cases_30d":       cases_30d.get(wid, 0),
            "dengue_cases_prev_year": cases_prev.get(wid, 0),
        }
        for wid in ward_ids
    }


def get_ward_metadata_from_db() -> dict[str, dict]:
    from db.client import get_supabase
    result = get_supabase().table("wards").select("id, population_density, population, area_sqkm").execute()
    return {
        row["id"]: {
            "population_density": row.get("population_density") or 10000,
            "population":         row.get("population") or 50000,
            "area_sqkm":          row.get("area_sqkm") or 2.0,
        }
        for row in result.data
    }
