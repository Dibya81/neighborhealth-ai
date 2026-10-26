"""Feature engineering for direct multi-horizon forecasting.

Row t of the design matrix uses ONLY information available at the end of week t (the forecast
origin) and its target is cases in week t+h. Every feature below is built with backward-looking
shifts/rollings, and `test_features.py` checks there is no look-ahead.

Feature groups (used to turn per-feature attributions into human-readable reasons):
  trend     recent case levels and growth
  seasonal  same weeks last year
  rain / temperature / humidity   weather in the weeks before the origin (mosquito breeding lags 2-8 weeks)
  testing   testing volume and positivity (case counts partly reflect testing effort)
  season    time of year of the target week
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_GROUPS: dict[str, str] = {}


def _reg(name: str, group: str) -> str:
    FEATURE_GROUPS[name] = group
    return name


GROUP_LABELS = {
    "trend": "Recent case trend",
    "seasonal": "Same time last year",
    "rain": "Rainfall in recent weeks",
    "temperature": "Temperature",
    "humidity": "Humidity",
    "testing": "Testing volume and positivity",
    "season": "Time of year",
}


def build_design(df: pd.DataFrame, h: int) -> tuple[pd.DataFrame, pd.Series]:
    """Return (X, y) aligned on origin week. y = cases at origin + h (NaN where unknown)."""
    c = df["cases"]
    lc = np.log1p(c)
    X = pd.DataFrame(index=df.index)

    for k in range(4):
        X[_reg(f"log_cases_lag{k}", "trend")] = lc.shift(k)
    ma4 = c.rolling(4, min_periods=2).mean()
    X[_reg("log_ma4", "trend")] = np.log1p(ma4)
    X[_reg("log_ma8", "trend")] = np.log1p(c.rolling(8, min_periods=4).mean())
    X[_reg("growth_4w", "trend")] = np.log1p(ma4) - np.log1p(ma4.shift(4))

    # value in the target week one year earlier: index t -> week t+h-52
    X[_reg("log_same_week_last_year", "seasonal")] = lc.shift(52 - h)
    X[_reg("log_last_year_window", "seasonal")] = np.log1p(c.rolling(3, center=True, min_periods=1).mean()).shift(52 - h)

    rain = df["rain_mm"]
    X[_reg("rain_4w", "rain")] = rain.rolling(4, min_periods=3).sum()
    X[_reg("rain_lag4_8w", "rain")] = rain.shift(4).rolling(4, min_periods=3).sum()
    X[_reg("rain_days_4w", "rain")] = df["rain_days"].rolling(4, min_periods=3).sum()
    X[_reg("temp_mean_4w", "temperature")] = df["temp_mean_c"].rolling(4, min_periods=3).mean()
    X[_reg("temp_min_4w", "temperature")] = df["temp_min_c"].rolling(4, min_periods=3).mean()
    X[_reg("rh_mean_4w", "humidity")] = df["rh_mean_pct"].rolling(4, min_periods=3).mean()

    tests = df["tests"]
    X[_reg("log_tests_2w", "testing")] = np.log1p(tests.rolling(2, min_periods=1).mean())
    pos = c.rolling(4, min_periods=2).sum() / tests.rolling(4, min_periods=2).sum()
    X[_reg("positivity_4w", "testing")] = pos.replace([np.inf, -np.inf], np.nan)

    target_week = (df.index + pd.Timedelta(weeks=h)).isocalendar().week.astype(float).values
    X[_reg("season_sin", "season")] = np.sin(2 * np.pi * target_week / 52.18)
    X[_reg("season_cos", "season")] = np.cos(2 * np.pi * target_week / 52.18)

    y = c.shift(-h)
    return X, y


def feature_names() -> list[str]:
    if not FEATURE_GROUPS:  # populate registry
        idx = pd.date_range("2020-01-05", periods=60, freq="W-SUN")
        dummy = pd.DataFrame({k: 1.0 for k in ["cases", "tests", "rain_mm", "rain_days", "temp_mean_c",
                                               "temp_max_c", "temp_min_c", "rh_mean_pct"]}, index=idx)
        build_design(dummy, 1)
    return list(FEATURE_GROUPS)
