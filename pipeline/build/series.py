"""Turn daily bulletin rows into a clean weekly case series for one area.

Why cumulative counts? Bulletins are missing on some days. Summing "on the day" numbers would
silently undercount those weeks. The year-to-date cumulative count doesn't have that problem:
weekly cases = cumulative(end of week) - cumulative(end of previous week), even across gaps.

Steps:
  1. Keep trusted rows that have a cumulative total.
  2. Remove points that break monotonicity within a year (extraction or typing errors),
     removing the most-offending point first until the series is non-decreasing.
  3. Chain years into one global cumulative (the bulletin resets on 1 January).
  4. Interpolate to daily, take Sunday values, difference -> weekly cases.
  5. Attach quality info: how many real observations fell in each week.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _remove_monotonic_violations(values: list[float], window: int = 6) -> list[bool]:
    """Return a keep-mask. Greedily drops the point involved in most local order violations."""
    keep = [True] * len(values)
    while True:
        idx = [i for i, k in enumerate(keep) if k]
        scores = {}
        for pos, i in enumerate(idx):
            later = idx[pos + 1: pos + 1 + window]
            earlier = idx[max(0, pos - window): pos]
            s = sum(values[j] < values[i] for j in later) + sum(values[j] > values[i] for j in earlier)
            if s:
                scores[i] = s
        if not scores:
            return keep
        worst = max(scores, key=lambda i: (scores[i], -i))
        keep[worst] = False


def clean_cumulative(rows: pd.DataFrame, area: str, value_col: str = "cum_total_pos") -> pd.DataFrame:
    day_col = value_col.replace("cum_", "day_")
    sub = rows[(rows["area"] == area) & (rows["trusted"]) & rows[value_col].notna()].copy()
    keep = ["date", value_col, day_col] + (["cum_year"] if "cum_year" in sub else [])
    sub = sub.sort_values("date")[keep].rename(columns={value_col: "cum_value", day_col: "day_value"})
    # Group by the year the cumulative refers to: bulletins dated early January can still be the
    # previous year's final ("supplementary") report, whose counts do not restart at zero.
    sub["year"] = sub["cum_year"].astype(int) if "cum_year" in sub else sub["date"].dt.year
    parts = []
    for _, g in sub.groupby("year"):
        mask = _remove_monotonic_violations(g["cum_value"].astype(float).tolist())
        g = g.assign(kept=mask)
        parts.append(g)
    out = pd.concat(parts) if parts else sub.assign(kept=[])
    return out


def build_weekly(rows: pd.DataFrame, area: str = "BBMP", value_col: str = "cum_total_pos") -> tuple[pd.DataFrame, dict]:
    obs = clean_cumulative(rows, area, value_col)
    report = {"area": area, "value": value_col, "n_rows": int(len(obs)), "n_removed_outliers": int((~obs["kept"]).sum()) if len(obs) else 0}
    obs = obs[obs["kept"]]
    if len(obs) < 3:
        return pd.DataFrame(), {**report, "error": "not enough trusted observations"}

    # Chain years: global = within-year cumulative + final totals of all previous years.
    offset, chained, year_end_gaps = 0.0, [], {}
    for year, g in obs.groupby("year"):
        g = g.copy()
        g["global_cum"] = g["cum_value"].astype(float) + offset
        last = g.iloc[-1]
        year_end_gaps[int(year)] = int((pd.Timestamp(year=int(year), month=12, day=31) - last["date"]).days)
        offset += float(last["cum_value"])
        chained.append(g)
    obs = pd.concat(chained)
    report["year_end_gap_days"] = year_end_gaps

    daily = obs.set_index("date")["global_cum"]
    full_idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full_idx).interpolate(method="time")

    weekly_cum = daily.resample("W-SUN").last()
    cases = weekly_cum.diff()
    n_obs = obs.set_index("date")["global_cum"].resample("W-SUN").count().reindex(weekly_cum.index, fill_value=0)
    day_sum = obs.set_index("date")["day_value"].resample("W-SUN").sum(min_count=1).reindex(weekly_cum.index)

    out = pd.DataFrame({
        "week_end": weekly_cum.index,
        "cases": cases.round(1).values,
        "global_cum": weekly_cum.values,
        "n_obs": n_obs.values,
        "sum_on_day_reports": day_sum.values,
    }).iloc[1:]  # first week has no previous value
    # A week that ends after the last real bulletin is not a week of data: its "cases" would just be the
    # cumulative carried forward (a spurious near-zero). Keep only weeks that end on or before the last observation.
    out = out[out["week_end"] <= obs["date"].max()]
    out["quality"] = np.select([out["n_obs"] >= 3, out["n_obs"] >= 1], ["ok", "partial"], default="interpolated")
    out["area"] = area

    full = out[out["n_obs"] == 7].dropna(subset=["sum_on_day_reports"])
    if len(full) >= 5:
        report["check_weekly_vs_on_day_corr"] = round(float(np.corrcoef(full["cases"], full["sum_on_day_reports"])[0, 1]), 3)
    report.update(n_weeks=int(len(out)), weeks_ok=int((out["quality"] == "ok").sum()),
                  start=str(out["week_end"].min().date()), end=str(out["week_end"].max().date()),
                  total_cases=float(out["cases"].sum()))
    return out.reset_index(drop=True), report
