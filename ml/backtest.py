"""Rolling-origin backtesting with leak-free conformal prediction intervals.

For every origin week t (after a minimum training period) and every horizon h:
  1. train each model on weeks <= t only,
  2. forecast week t+h,
  3. compare with what actually happened.
This simulates running the system live, week by week, which is the only honest way to evaluate
a forecaster. (A single random train/test split would leak the future into training.)

Prediction intervals: online split-conformal on log-scale residuals. The interval for a forecast
made at origin t uses only residuals of forecasts whose target week was already observed at t.
So the reported coverage is what a user would really have experienced.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml import HORIZONS, INTERVAL_LEVELS
from ml.models import make_model

ENSEMBLE_MEMBERS = ("glm_poisson", "gbm", "sarima")


def rolling_backtest(df: pd.DataFrame, model_names: list[str], horizons=HORIZONS, min_train: int = 78,
                     refit_every: int = 1, progress: bool = False,
                     scored_weeks: pd.Series | None = None) -> pd.DataFrame:
    """scored_weeks: optional boolean Series (indexed like df). Target weeks where it is False were
    filled in by interpolation across missing bulletins, so they are not real observations: their
    y_true is set to NaN and they are excluded from scoring and from the conformal residuals.
    Models are still trained on every week."""
    n = len(df)
    weeks = df.index
    rows = []
    base_names = [m for m in model_names if m != "ensemble"]
    for name in base_names:
        for h in horizons:
            model = make_model(name)
            for t in range(min_train, n - h):
                if (t - min_train) % refit_every == 0:
                    model.fit(df, h, t)
                try:
                    pred = model.predict(df, h, t)
                except Exception:
                    pred = np.nan
                rows.append({"model": name, "horizon": h, "origin": weeks[t], "target_week": weeks[t + h],
                             "y_true": (df["cases"].iloc[t + h]
                                        if scored_weeks is None or bool(scored_weeks.iloc[t + h]) else np.nan),
                             "y_pred": max(pred, 0.0) if pred == pred else np.nan})
            if progress:
                print(f"  backtest {name} h={h}: {n - h - min_train} origins")
    preds = pd.DataFrame(rows)
    if "ensemble" in model_names and not preds.empty:
        members = [m for m in ENSEMBLE_MEMBERS if m in base_names]
        if len(members) >= 2:
            wide = preds[preds["model"].isin(members)].pivot_table(
                index=["horizon", "origin", "target_week", "y_true"], columns="model", values="y_pred").dropna()
            ens = np.expm1(np.log1p(wide.clip(lower=0)).mean(axis=1)).rename("y_pred").reset_index()
            ens["model"] = "ensemble"
            preds = pd.concat([preds, ens], ignore_index=True)
    return add_conformal_intervals(preds)


def _quantile_pair(res: np.ndarray, level: float) -> tuple[float, float]:
    a = (1 - level) / 2
    return float(np.quantile(res, a)), float(np.quantile(res, 1 - a))


def add_conformal_intervals(preds: pd.DataFrame, window: int = 52, min_residuals: int = 8) -> pd.DataFrame:
    preds = preds.sort_values(["model", "horizon", "origin"]).reset_index(drop=True)
    for l in INTERVAL_LEVELS:
        preds[f"lo{int(l * 100)}"] = np.nan
        preds[f"hi{int(l * 100)}"] = np.nan
    for (_, _), g in preds.groupby(["model", "horizon"]):
        log_res = np.log1p(g["y_true"].values) - np.log1p(g["y_pred"].values)
        targets = g["target_week"].values
        for pos, (idx, row) in enumerate(g.iterrows()):
            known = (targets[:pos] <= row["origin"]) & ~np.isnan(log_res[:pos])
            res = log_res[:pos][known][-window:]
            if len(res) < min_residuals or np.isnan(row["y_pred"]):
                continue
            centre = np.log1p(row["y_pred"])
            for l in INTERVAL_LEVELS:
                qlo, qhi = _quantile_pair(res, l)
                preds.at[idx, f"lo{int(l * 100)}"] = max(np.expm1(centre + qlo), 0.0)
                preds.at[idx, f"hi{int(l * 100)}"] = max(np.expm1(centre + qhi), 0.0)
    return preds


def interval_from_history(preds: pd.DataFrame, model: str, h: int, point: float, window: int = 52) -> dict:
    """Interval for a live forecast, from that model's most recent backtest residuals."""
    g = preds[(preds["model"] == model) & (preds["horizon"] == h)].dropna(subset=["y_true", "y_pred"])
    g = g.sort_values("target_week").tail(window)
    out = {"median": point}
    if len(g) < 8:
        return out
    res = np.log1p(g["y_true"].values) - np.log1p(g["y_pred"].values)
    centre = np.log1p(point)
    for l in INTERVAL_LEVELS:
        qlo, qhi = _quantile_pair(res, l)
        out[f"lo{int(l * 100)}"] = max(float(np.expm1(centre + qlo)), 0.0)
        out[f"hi{int(l * 100)}"] = max(float(np.expm1(centre + qhi)), 0.0)
    return out


def choose_champion(scores: pd.DataFrame, exclude=("persistence", "seasonal_naive")) -> str:
    """Lowest mean WIS across horizons (MAE if intervals are unavailable), excluding baselines."""
    cand = scores[~scores["model"].isin(exclude)]
    if cand.empty:
        return "seasonal_naive"
    metric = "wis" if "wis" in cand and cand["wis"].notna().all() else "mae"
    return str(cand.groupby("model")[metric].mean().idxmin())
