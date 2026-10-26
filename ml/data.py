"""Load the weekly modelling table produced by the Step 1 pipeline."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from pipeline.config import get_paths, load_city

WEATHER_COLS = ["rain_mm", "rain_days", "temp_mean_c", "temp_max_c", "temp_min_c", "rh_mean_pct"]


def load_table(processed_dir: Path | None = None) -> pd.DataFrame:
    """One row per week (ending Sunday): cases, tests, weather. Index = week_end."""
    processed_dir = processed_dir or get_paths().processed
    target = load_city()["surveillance"]["target_area"].lower()
    cases = pd.read_csv(processed_dir / f"{target}_weekly_cases.csv", parse_dates=["week_end"])
    df = cases[["week_end", "cases", "quality", "n_obs"]].set_index("week_end")

    tests_path = processed_dir / f"{target}_weekly_tests.csv"
    if tests_path.exists():
        tests = pd.read_csv(tests_path, parse_dates=["week_end"]).set_index("week_end")["tests"]
        df = df.join(tests, how="left")
    else:
        df["tests"] = float("nan")

    wx_path = processed_dir / "weather_weekly.csv"
    if wx_path.exists():
        wx = pd.read_csv(wx_path, parse_dates=["week_end"]).set_index("week_end")[WEATHER_COLS]
        df = df.join(wx, how="left")
    else:
        for c in WEATHER_COLS:
            df[c] = float("nan")

    df = df.asfreq("W-SUN")  # make gaps explicit
    df["cases"] = df["cases"].clip(lower=0)
    return df
