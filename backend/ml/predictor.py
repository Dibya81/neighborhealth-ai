from __future__ import annotations
import numpy as np
import pandas as pd
from functools import lru_cache
from pathlib import Path
from utils.logger import get_logger
from ml.rule_based import compute_rule_based_score, build_rule_based_ward_scores

logger = get_logger(__name__)

MODEL_PATH = Path(__file__).parent / "model" / "xgb_dengue.pkl"


@lru_cache(maxsize=1)
def _load_dengue_model():
    if MODEL_PATH.exists():
        import joblib
        logger.info("Loading Dengue ML model from %s", MODEL_PATH)
        return joblib.load(MODEL_PATH)
    logger.warning("ML model not found at %s — rule-based fallback active.", MODEL_PATH)
    return None


def predict_risk_scores(feature_df: pd.DataFrame, disease_id: str, ward_metadata: dict = None) -> pd.DataFrame:
    if disease_id == "dengue":
        return _predict_dengue_ml(feature_df)
    if disease_id == "malaria":
        return _predict_malaria_hybrid(feature_df)
    return _predict_rule_based(feature_df, disease_id, ward_metadata)


def _predict_dengue_ml(feature_df: pd.DataFrame) -> pd.DataFrame:
    model = _load_dengue_model()
    if model is None:
        return _predict_rule_based(feature_df, "dengue", None)

    raw_probs = model.predict_proba(feature_df)[:, 1]
    scores    = (raw_probs * 100).clip(0, 100)

    result = pd.DataFrame({
        "ward_id":   feature_df.index,
        "risk_score": np.round(scores, 2),
    })
    result["risk_level"] = result["risk_score"].apply(_level)
    result["ai_reason"]  = [
        _explain("dengue", s, feature_df.loc[w])
        for w, s in zip(result["ward_id"], result["risk_score"])
    ]
    return result


def _predict_malaria_hybrid(feature_df: pd.DataFrame) -> pd.DataFrame:
    dengue_df   = _predict_dengue_ml(feature_df)
    rain_signal = (feature_df["rainfall_7d"] / 80.0).clip(0, 1) * 100
    hybrid      = dengue_df["risk_score"] * 0.8 + rain_signal.values * 0.2

    result = pd.DataFrame({
        "ward_id":   feature_df.index,
        "risk_score": np.round(hybrid, 2),
    })
    result["risk_level"] = result["risk_score"].apply(_level)
    result["ai_reason"]  = [
        _explain("malaria", s, feature_df.loc[w])
        for w, s in zip(result["ward_id"], result["risk_score"])
    ]
    return result


def _predict_rule_based(feature_df: pd.DataFrame, disease_id: str, ward_metadata: dict) -> pd.DataFrame:
    weather = {
        "rainfall_7d": float(feature_df["rainfall_7d"].iloc[0]),
        "temp_avg":    float(feature_df["temp_avg"].iloc[0]),
        "humidity_avg":float(feature_df["humidity_avg"].iloc[0]),
    }
    base_score = compute_rule_based_score(disease_id, weather)
    meta       = ward_metadata or {wid: {} for wid in feature_df.index}
    result     = build_rule_based_ward_scores(base_score, meta)
    result["ai_reason"] = [
        _explain(disease_id, row["risk_score"], feature_df.loc[row["ward_id"]])
        if row["ward_id"] in feature_df.index else ["No feature data available."]
        for _, row in result.iterrows()
    ]
    return result


def _explain(disease_id: str, score: float, features: pd.Series) -> list[str]:
    reasons = []
    if score >= 70:   reasons.append("Critical risk level — take immediate precautions.")
    elif score >= 40: reasons.append("Moderate risk conditions present.")
    else:             reasons.append("Environmental risk currently low.")

    rain = features.get("rainfall_7d", 0) if hasattr(features, "get") else getattr(features, "rainfall_7d", 0)
    temp = features.get("temp_avg",    27) if hasattr(features, "get") else getattr(features, "temp_avg", 27)
    rpts = features.get("report_count_7d", 0) if hasattr(features, "get") else getattr(features, "report_count_7d", 0)

    if float(rain) > 40: reasons.append(f"Heavy rainfall ({rain:.1f}mm) — stagnant water risk elevated.")
    if float(temp) > 32: reasons.append(f"High temperature ({temp:.1f}°C) — pathogen incubation accelerated.")
    if float(rpts) > 5:  reasons.append(f"Community reports spike ({int(rpts)}) — active breeding sites confirmed.")
    if disease_id == "malaria":
        reasons.append("Malaria risk correlates with dengue patterns and surface water accumulation.")
    return reasons


def _level(score: float) -> str:
    if score < 40: return "low"
    if score < 70: return "medium"
    return "high"


def get_model_version() -> str:
    import json
    try:
        meta_path = MODEL_PATH.parent / "model_metadata.json"
        if meta_path.exists():
            return json.loads(meta_path.read_text()).get("model_version", "v2-no-leakage")
    except Exception:
        pass
    return "v2-no-leakage"
