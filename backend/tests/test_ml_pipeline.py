import pytest
import numpy as np
import pandas as pd
from datetime import date
from ml.features import get_same_day_prev_year, FEATURE_COLUMNS
from ml.predictor import _load_dengue_model, predict_risk_scores
from utils.cache import InMemoryCache


def test_leap_year_handling():
    # Leap day in leap year 2024 -> must safely map to Feb 28, 2023
    feb29_2024 = date(2024, 2, 29)
    prev_year = get_same_day_prev_year(feb29_2024)
    assert prev_year == date(2023, 2, 28)

    # Feb 28 in leap year 2024 -> maps to Feb 28, 2023
    feb28_2024 = date(2024, 2, 28)
    assert get_same_day_prev_year(feb28_2024) == date(2023, 2, 28)

    # March 1 in leap year 2024 -> maps to March 1, 2023
    mar1_2024 = date(2024, 3, 1)
    assert get_same_day_prev_year(mar1_2024) == date(2023, 3, 1)

    # New Year Jan 1 boundary
    jan1_2025 = date(2025, 1, 1)
    assert get_same_day_prev_year(jan1_2025) == date(2024, 1, 1)

    # Year end Dec 31 boundary
    dec31_2024 = date(2024, 12, 31)
    assert get_same_day_prev_year(dec31_2024) == date(2023, 12, 31)


def test_model_loading_and_inference():
    model = _load_dengue_model()
    assert model is not None, "Dengue ML model failed to load"

    # Create synthetic test feature rows adhering strictly to FEATURE_COLUMNS
    test_data = {
        "rainfall_7d": [12.5, 85.0, 0.0],
        "rainfall_lag14": [20.0, 110.0, 0.0],
        "temp_avg": [26.5, 29.0, 31.0],
        "humidity_avg": [70.0, 88.0, 45.0],
        "dengue_cases_30d": [5, 45, 0],
        "dengue_cases_prev_year": [10, 60, 2],
        "report_count_7d": [1, 15, 0],
        "month": [9, 10, 3],
        "population_density": [12000.0, 28000.0, 5000.0],
    }
    df = pd.DataFrame(test_data, index=["1", "2", "3"])[FEATURE_COLUMNS]

    probs = model.predict_proba(df)
    assert probs.shape == (3, 2)
    # Check probability axioms
    assert np.all(probs >= 0.0)
    assert np.all(probs <= 1.0)
    assert np.allclose(probs.sum(axis=1), 1.0)

    # Test risk score predictor wrapper
    pred_df = predict_risk_scores(df, "dengue")
    assert "risk_score" in pred_df.columns
    assert "risk_level" in pred_df.columns
    assert "ai_reason" in pred_df.columns
    assert np.all(pred_df["risk_score"] >= 0.0)
    assert np.all(pred_df["risk_score"] <= 100.0)


def test_cache_prefix_invalidation():
    cache = InMemoryCache()
    cache.set("risk:all:dengue", {"scores": [1, 2, 3]}, ttl_seconds=3600)
    cache.set("risk:all:malaria", {"scores": [4, 5, 6]}, ttl_seconds=3600)
    cache.set("wards:all", {"wards": ["1", "2"]}, ttl_seconds=3600)

    assert cache.get("risk:all:dengue") is not None
    assert cache.get("risk:all:malaria") is not None
    assert cache.get("wards:all") is not None

    # Invalidate prefix "risk:"
    invalidated_count = cache.delete_prefix("risk:")
    assert invalidated_count == 2
    assert cache.get("risk:all:dengue") is None
    assert cache.get("risk:all:malaria") is None
    # Unrelated cache key remains intact
    assert cache.get("wards:all") is not None
