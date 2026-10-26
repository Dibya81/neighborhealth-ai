"""Data-drift checks: Population Stability Index (PSI) of recent features vs the training period.

PSI < 0.1 stable · 0.1–0.25 moderate shift · > 0.25 significant shift (common industry rule of thumb).
A drift flag doesn't block anything by itself; it tells you to look before trusting the forecast.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def psi(reference: np.ndarray, current: np.ndarray, bins: int = 10) -> float | None:
    ref = reference[~np.isnan(reference)]
    cur = current[~np.isnan(current)]
    if len(ref) < 20 or len(cur) < 4:
        return None
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return None
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.histogram(ref, edges)[0] / len(ref)
    c = np.histogram(cur, edges)[0] / len(cur)
    r, c = np.clip(r, 1e-4, None), np.clip(c, 1e-4, None)
    return float(((c - r) * np.log(c / r)).sum())


def drift_report(X: pd.DataFrame, recent_weeks: int = 12) -> dict:
    ref, cur = X.iloc[:-recent_weeks], X.iloc[-recent_weeks:]
    out = {}
    for col in X.columns:
        v = psi(ref[col].values.astype(float), cur[col].values.astype(float))
        if v is None:
            continue
        out[col] = {"psi": round(v, 3), "status": "significant" if v > 0.25 else "moderate" if v > 0.1 else "stable"}
    flagged = [k for k, v in out.items() if v["status"] == "significant"]
    return {"recent_weeks": recent_weeks, "features": out, "significant": flagged,
            "overall": "drift" if flagged else "ok"}
