"""Per-forecast explanations (SHAP values), grouped into human-readable factors.

All attributions are on the log scale of expected cases, so they add up:
    log(forecast) = baseline + sum(contributions)
and a contribution of c means "this factor multiplies the forecast by exp(c)".

Methods:
  * LightGBM: exact TreeSHAP via `pred_contrib=True` (built into LightGBM).
  * Poisson GLM: exact linear SHAP: beta_j * (x_j - mean_j) on standardised inputs.
  * anything else: Monte-Carlo permutation Shapley with a background sample (model-agnostic).
These factor lists are the ONLY material the AI assistant may use to explain a forecast.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.features import FEATURE_GROUPS, GROUP_LABELS
from ml.models import GBM, GLMPoisson


def _sampling_shapley(f, x: pd.DataFrame, background: pd.DataFrame, n_perm: int = 64, seed: int = 0):
    rng = np.random.default_rng(seed)
    cols = list(x.columns)
    d = len(cols)
    phi = np.zeros(d)
    xv = x.iloc[0].values
    bg = background.values
    for _ in range(n_perm):
        order = rng.permutation(d)
        z = bg[rng.integers(len(bg))].copy()
        prev = f(pd.DataFrame([z], columns=cols))[0]
        for j in order:
            z[j] = xv[j]
            cur = f(pd.DataFrame([z], columns=cols))[0]
            phi[j] += cur - prev
            prev = cur
    phi /= n_perm
    base = float(np.mean(f(background)))
    return base, phi


def feature_contributions(model, x: pd.DataFrame) -> tuple[float, pd.Series, str]:
    """Returns (baseline_log, contributions per feature, method)."""
    x = x[model.columns]
    if isinstance(model, GBM) and model.backend == "lightgbm":
        contrib = model.model.predict(x, pred_contrib=True)[0]
        return float(contrib[-1]), pd.Series(contrib[:-1], index=model.columns), "TreeSHAP (LightGBM native)"
    if isinstance(model, GLMPoisson):
        imputer, scaler, glm = (model.model.named_steps[k] for k in ("simpleimputer", "standardscaler", "poissonregressor"))
        z = scaler.transform(imputer.transform(x))[0]
        bg = scaler.transform(imputer.transform(model.background))
        contrib = glm.coef_ * (z - bg.mean(axis=0))
        base = float(glm.intercept_ + glm.coef_ @ bg.mean(axis=0))
        return base, pd.Series(contrib, index=model.columns), "Exact linear SHAP (Poisson GLM)"
    base, phi = _sampling_shapley(model.log_predict, x, model.background.fillna(model.background.median()))
    return base, pd.Series(phi, index=model.columns), "Permutation Shapley (model-agnostic)"


def group_factors(contrib: pd.Series, x: pd.DataFrame, top: int = 5) -> list[dict]:
    groups: dict[str, float] = {}
    for feat, val in contrib.items():
        groups[FEATURE_GROUPS.get(feat, "other")] = groups.get(FEATURE_GROUPS.get(feat, "other"), 0.0) + float(val)
    factors = []
    for g, v in sorted(groups.items(), key=lambda kv: -abs(kv[1])):
        feats = [f for f in contrib.index if FEATURE_GROUPS.get(f) == g]
        factors.append({
            "factor": g,
            "label": GROUP_LABELS.get(g, g),
            "effect_log": round(v, 4),
            "effect_pct": round(float(np.expm1(v) * 100), 1),     # "+35%" = pushes forecast up 35%
            "direction": "up" if v > 0 else "down",
            "evidence": {f: (None if pd.isna(x.iloc[0][f]) else round(float(x.iloc[0][f]), 3)) for f in feats},
        })
    return factors[:top]


def explain_forecast(model, x: pd.DataFrame) -> dict:
    base, contrib, method = feature_contributions(model, x)
    return {"method": method, "baseline_cases": round(float(np.exp(base)), 1),
            "factors": group_factors(contrib, x[model.columns])}
