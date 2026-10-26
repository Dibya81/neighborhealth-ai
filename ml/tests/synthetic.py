"""Synthetic weekly data for TESTS ONLY (never used for real results).
Cases follow seasonal rain with a ~4-week lag plus negative-binomial noise, so a correct model
should learn the rain signal and beat the seasonal-naive baseline."""
from __future__ import annotations

import numpy as np
import pandas as pd


def make_weekly(n_weeks: int = 208, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2021-01-03", periods=n_weeks, freq="W-SUN")
    woy = idx.isocalendar().week.astype(float).values
    year_amp = rng.uniform(0.6, 1.6, size=n_weeks // 52 + 2)[(np.arange(n_weeks) // 52)]
    rain = np.clip(60 * year_amp * np.maximum(0, np.sin(2 * np.pi * (woy - 18) / 52)) + rng.gamma(2, 6, n_weeks), 0, None)
    temp = 24 + 3 * np.sin(2 * np.pi * (woy - 10) / 52) + rng.normal(0, 0.5, n_weeks)
    rh = 60 + 20 * np.sin(2 * np.pi * (woy - 22) / 52) + rng.normal(0, 3, n_weeks)
    lagged_rain = pd.Series(rain).rolling(4, min_periods=1).mean().shift(4).fillna(rain.mean()).values
    mu = np.exp(2.5 + 0.035 * lagged_rain)
    cases = rng.negative_binomial(n=8, p=8 / (8 + mu)).astype(float)
    tests = np.round(cases * rng.uniform(3, 5, n_weeks) + 200)
    return pd.DataFrame({"cases": cases, "quality": "ok", "n_obs": 6, "tests": tests, "rain_mm": rain,
                         "rain_days": np.minimum(7, rain / 8).round(), "temp_mean_c": temp, "temp_max_c": temp + 6,
                         "temp_min_c": temp - 6, "rh_mean_pct": rh}, index=idx)
