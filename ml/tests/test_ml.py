import json
import math

import numpy as np
import pandas as pd

from ml.backtest import add_conformal_intervals, choose_champion, rolling_backtest
from ml.explain import explain_forecast, feature_contributions
from ml.features import build_design
from ml.metrics import score_predictions, wis
from ml.models import GBM, GLMPoisson, SeasonalNaive
from ml.tests.synthetic import make_weekly
from ml.wards import allocate, point_in_ring, ring_area_centroid


def test_features_have_no_lookahead():
    df = make_weekly()
    X1, _ = build_design(df, 2)
    future_changed = df.copy()
    future_changed.iloc[121:, :] = future_changed.iloc[121:, :].assign(cases=9999, rain_mm=9999, tests=1)
    X2, _ = build_design(future_changed, 2)
    row = 120
    pd.testing.assert_series_equal(X1.iloc[row], X2.iloc[row], check_names=False)


def test_seasonal_naive_uses_last_year():
    df = make_weekly()
    t, h = 120, 2
    expected = df["cases"].iloc[t + h - 53: t + h - 50].mean()
    assert math.isclose(SeasonalNaive().predict(df, h, t), expected)


def test_backtest_scores_and_ml_beats_baseline():
    df = make_weekly()
    preds = rolling_backtest(df, ["persistence", "seasonal_naive", "glm_poisson", "gbm", "ensemble"],
                             horizons=(1, 2), min_train=104, refit_every=4)
    scores = score_predictions(preds)
    assert set(scores["model"]) == {"persistence", "seasonal_naive", "glm_poisson", "gbm", "ensemble"}
    glm = scores[scores["model"] == "glm_poisson"]
    assert (glm["skill_vs_seasonal_naive"] > 0).all(), scores
    cov = scores.dropna(subset=["coverage80"])["coverage80"]
    assert ((cov > 0.5) & (cov <= 1.0)).all(), scores
    assert choose_champion(scores) in {"glm_poisson", "gbm", "ensemble"}


def test_conformal_intervals_never_use_future_residuals():
    preds = pd.DataFrame({
        "model": "m", "horizon": 1,
        "origin": pd.date_range("2022-01-02", periods=30, freq="W-SUN"),
        "y_true": np.r_[np.full(20, 10.0), np.full(10, 1000.0)], "y_pred": 10.0})
    preds["target_week"] = preds["origin"] + pd.Timedelta(weeks=1)
    out = add_conformal_intervals(preds)
    assert out["lo80"].iloc[:8].isna().all()         # not enough history yet
    # At origin 20 the huge errors (targets at weeks 21+) are not yet observable:
    assert out["hi80"].iloc[20] < 20


def test_wis_perfect_forecast_is_zero():
    y = np.array([10.0, 20.0])
    assert np.allclose(wis(y, y, {0.8: (y, y)}), 0)


def test_glm_explanations_add_up():
    df = make_weekly()
    m = GLMPoisson().fit(df, 1, 180)
    X, _ = build_design(df, 1)
    x = X.iloc[[180]]
    base, contrib, _ = feature_contributions(m, x)
    assert math.isclose(base + contrib.sum(), float(m.log_predict(x)[0]), rel_tol=1e-6)
    ex = explain_forecast(m, x)
    assert ex["factors"] and {"label", "effect_pct", "evidence"} <= set(ex["factors"][0])
    json.dumps(ex)  # must be serialisable for the API


def test_gbm_shapley_approximately_efficient():
    df = make_weekly()
    m = GBM(backend="sklearn").fit(df, 1, 180)
    X, _ = build_design(df, 1)
    x = X.iloc[[180]]
    base, contrib, method = feature_contributions(m, x)
    assert "Shapley" in method
    assert abs((base + contrib.sum()) - float(m.log_predict(x)[0])) < 0.15


def test_polygon_area_and_point_in_polygon():
    # ~1.11 km x 1.11 km square at the equator-ish latitude of Bengaluru
    ring = [[77.0, 13.0], [77.01, 13.0], [77.01, 13.01], [77.0, 13.01], [77.0, 13.0]]
    area, cx, cy = ring_area_centroid(ring, 13.0)
    assert 1.15 < area < 1.25 and math.isclose(cx, 77.005, abs_tol=1e-6)
    assert point_in_ring(77.005, 13.005, ring) and not point_in_ring(77.02, 13.005, ring)


def test_allocation_conserves_city_total_and_uses_reports():
    wards = pd.DataFrame({"ward_id": ["1", "2", "3"], "ward_name": list("abc"), "population_est": [1e5, 1e5, 2e5],
                          "density_est": [1e4, 1e4, 1e4], "lat": 0, "lon": 0})
    fc = {"median": 100.0, "lo80": 80.0, "hi80": 125.0}
    out = allocate(wards, fc, n_sims=2000)
    assert 85 < out["expected_cases"].sum() < 115
    assert out.loc[2, "expected_cases"] > out.loc[0, "expected_cases"]
    with_reports = allocate(wards, fc, reports=pd.Series({"1": 20}), n_sims=2000)
    assert with_reports.loc[0, "expected_cases"] > out.loc[0, "expected_cases"]
    assert set(out["uncertainty"]) <= {"low", "medium", "high"}
