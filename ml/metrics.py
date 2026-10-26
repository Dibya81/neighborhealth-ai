"""Forecast scoring. WIS is the standard used by the US CDC FluSight / COVID-19 Forecast Hub."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml import INTERVAL_LEVELS


def interval_score(y, lo, hi, alpha):
    y, lo, hi = map(np.asarray, (y, lo, hi))
    return (hi - lo) + (2 / alpha) * (lo - y) * (y < lo) + (2 / alpha) * (y - hi) * (y > hi)


def wis(y, median, intervals: dict[float, tuple]) -> np.ndarray:
    """Weighted interval score. intervals: {level: (lo, hi)} e.g. {0.8: (lo80, hi80)}."""
    y, median = np.asarray(y, float), np.asarray(median, float)
    total = 0.5 * np.abs(y - median)
    for level, (lo, hi) in intervals.items():
        alpha = 1 - level
        total = total + (alpha / 2) * interval_score(y, lo, hi, alpha)
    return total / (len(intervals) + 0.5)


def score_predictions(preds: pd.DataFrame) -> pd.DataFrame:
    """preds columns: model, horizon, y_true, y_pred, lo50/hi50/lo80/hi80/lo95/hi95 (may be NaN)."""
    rows = []
    for (model, h), g in preds.dropna(subset=["y_true", "y_pred"]).groupby(["model", "horizon"]):
        err = g["y_pred"] - g["y_true"]
        rec = {"model": model, "horizon": int(h), "n": len(g),
               "mae": float(err.abs().mean()), "rmse": float(np.sqrt((err ** 2).mean())),
               "bias": float(err.mean())}
        gi = g.dropna(subset=[f"lo{int(l * 100)}" for l in INTERVAL_LEVELS])
        if len(gi):
            ivs = {l: (gi[f"lo{int(l * 100)}"], gi[f"hi{int(l * 100)}"]) for l in INTERVAL_LEVELS}
            rec["wis"] = float(wis(gi["y_true"], gi["y_pred"], ivs).mean())
            rec["n_interval"] = len(gi)
            for l in INTERVAL_LEVELS:
                k = int(l * 100)
                rec[f"coverage{k}"] = float(((gi["y_true"] >= gi[f"lo{k}"]) & (gi["y_true"] <= gi[f"hi{k}"])).mean())
        rows.append(rec)
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    # Skill relative to the seasonal-naive baseline, on MAE: positive = better than baseline.
    base = out[out["model"] == "seasonal_naive"].set_index("horizon")["mae"]
    out["skill_vs_seasonal_naive"] = out.apply(
        lambda r: 1 - r["mae"] / base.get(r["horizon"], np.nan) if base.get(r["horizon"], 0) else np.nan, axis=1)
    pers = out[out["model"] == "persistence"].set_index("horizon")["mae"]
    out["skill_vs_persistence"] = out.apply(
        lambda r: 1 - r["mae"] / pers.get(r["horizon"], np.nan) if pers.get(r["horizon"], 0) else np.nan, axis=1)
    return out.sort_values(["horizon", "model"]).reset_index(drop=True)
