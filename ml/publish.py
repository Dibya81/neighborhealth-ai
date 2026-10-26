"""Produce the live forecast bundle the API and frontend read: data/v2/forecasts/latest.json.

Contents: city history, 1-4 week forecasts with 50/80/95% intervals, SHAP-based drivers, ward
estimates per horizon (with uncertainty), backtest summary vs baselines, drift status, and provenance.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ml import HORIZONS
from ml.backtest import interval_from_history
from ml.data import load_table
from ml.drift import drift_report
from ml.explain import explain_forecast
from ml.features import build_design
from ml.models import GBM, Ensemble, GLMPoisson, make_model
from ml.wards import allocate, bands_from_history, estimate_population, load_wards
from pipeline.config import REPO_ROOT, get_paths, load_city


def forecasts_dir() -> Path:
    d = get_paths().root / "forecasts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _explainer(model):
    """Explanations come from a single interpretable member when the champion is an ensemble."""
    if isinstance(model, Ensemble):
        for pref in (GBM, GLMPoisson):
            for m in model.members:
                if isinstance(m, pref):
                    return m
        return None
    return model if isinstance(model, (GBM, GLMPoisson)) else None


def _ward_inputs():
    cfg = load_city()
    geo = REPO_ROOT / cfg["geography"]["wards_geojson"]
    census = pd.read_csv(REPO_ROOT / cfg["geography"]["ward_demographics_csv"])
    cache = get_paths().processed / "wards_estimated.csv"
    if cache.exists():
        wards = pd.read_csv(cache, dtype={"ward_id": str})
    else:
        wards = estimate_population(load_wards(geo), census)
        wards.to_csv(cache, index=False)
    reports_csv = get_paths().processed / "verified_reports_by_ward.csv"
    reports = None
    if reports_csv.exists():
        r = pd.read_csv(reports_csv, dtype={"ward_id": str})
        reports = r.set_index("ward_id")["reports_4w"]
    return wards, reports


def publish(champion_type: str, backtest: pd.DataFrame, scores: pd.DataFrame, model_version: str | None,
            df: pd.DataFrame | None = None) -> dict:
    df = df if df is not None else load_table()
    last = int(np.where(df["cases"].notna())[0].max())
    origin = df.index[last]

    forecasts, drivers, explainer_name = [], None, None
    for h in HORIZONS:
        model = make_model(champion_type).fit(df, h, last)
        point = model.predict(df, h, last)
        iv = interval_from_history(backtest, champion_type, h, point)
        forecasts.append({"horizon": h, "week_end": (origin + pd.Timedelta(weeks=h)).date().isoformat(),
                          **{k: round(v, 1) for k, v in iv.items()}})
        if h == 1:
            ex = _explainer(model)
            if ex is not None:
                X, _ = build_design(df, h)
                drivers = explain_forecast(ex, X.iloc[[last]])
                explainer_name = ex.name

    hist = df["cases"].iloc[max(0, last - 155): last + 1]
    city_pop = None
    wards_out = {}
    bands = None
    try:
        wards, reports = _ward_inputs()
        city_pop = float(wards["population_est"].sum())
        rate_hist = (df["cases"] / city_pop * 1e5).values
        bands = bands_from_history(rate_hist)
        for fc in forecasts:
            alloc = allocate(wards, fc, reports=reports, bands=bands, seed=fc["horizon"])
            wards_out[str(fc["horizon"])] = alloc.drop(columns=["lat", "lon"]).to_dict(orient="records")
    except FileNotFoundError as e:
        wards_out = {"error": str(e)}

    X1, _ = build_design(df, 1)
    summary_cols = ["model", "horizon", "mae", "wis", "coverage50", "coverage80", "coverage95",
                    "skill_vs_seasonal_naive", "skill_vs_persistence", "n"]
    bundle = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "city": load_city()["city"],
        "target": "Weekly lab-confirmed dengue cases reported for BBMP (Karnataka NVBDCP bulletins)",
        "model": {"version": model_version, "type": champion_type, "explanations_from": explainer_name},
        "origin_week": origin.date().isoformat(),
        "population_est": city_pop,
        "bands_per_100k": bands,
        "history": [{"week_end": i.date().isoformat(), "cases": None if pd.isna(v) else round(float(v), 1),
                     "rain_mm": None if pd.isna(df.at[i, "rain_mm"]) else round(float(df.at[i, "rain_mm"]), 1),
                     # how well this week is backed by real bulletins: ok | partial | interpolated
                     "quality": df.at[i, "quality"] if "quality" in df and isinstance(df.at[i, "quality"], str) else None}
                    for i, v in hist.items()],
        "forecast": forecasts,
        "drivers": drivers,
        "wards": wards_out,
        "backtest": scores[[c for c in summary_cols if c in scores.columns]].round(4).to_dict(orient="records"),
        "drift": drift_report(X1.iloc[: last + 1]),
        "disclaimer": ("Forecasts are of REPORTED cases for BBMP as a whole. Ward values are model estimates "
                       "(population x risk factors), not observed ward counts."),
    }
    out = forecasts_dir() / "latest.json"
    text = json.dumps(bundle, indent=1, default=str)
    out.write_text(text)
    (forecasts_dir() / f"forecast_{origin.date().isoformat()}.json").write_text(text)
    return bundle
