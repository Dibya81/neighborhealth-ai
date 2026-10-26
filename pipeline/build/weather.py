"""Weekly weather features from NASA POWER daily data (raw JSON, as served by the API).

Sources merged in order (later files win on overlapping dates):
  1. backend/data/raw/nasa_power_bengaluru_daily_2015_2024.json  (kept from v1)
  2. data/v2/raw/weather/*.json                                   (fetched with `fetch_nasa_power`)
"""
from __future__ import annotations

import json
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from pipeline.config import REPO_ROOT, get_paths, load_city

PARAMS = ["T2M", "T2M_MAX", "T2M_MIN", "RH2M", "PRECTOTCORR"]
API = ("https://power.larc.nasa.gov/api/temporal/daily/point?parameters={params}&community=AG"
       "&longitude={lon}&latitude={lat}&start={start}&end={end}&format=JSON")


def weather_dir() -> Path:
    d = get_paths().root / "raw" / "weather"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch_nasa_power(start: date, end: date) -> Path:
    """Download daily point data for the city centre. Run on a machine with internet access."""
    city = load_city()["city"]
    url = API.format(params=",".join(PARAMS), lon=city["lon"], lat=city["lat"],
                     start=start.strftime("%Y%m%d"), end=end.strftime("%Y%m%d"))
    with urllib.request.urlopen(url, timeout=120) as resp:
        body = resp.read()
    out = weather_dir() / f"nasa_power_{start:%Y%m%d}_{end:%Y%m%d}.json"
    out.write_bytes(body)
    return out


def _load_one(path: Path) -> pd.DataFrame:
    d = json.loads(path.read_text())
    fill = d.get("header", {}).get("fill_value", -999.0)
    params = d["properties"]["parameter"]
    df = pd.DataFrame({k: pd.Series(v) for k, v in params.items() if k in PARAMS})
    df.index = pd.to_datetime(df.index, format="%Y%m%d")
    return df.replace(fill, np.nan)


def load_daily() -> pd.DataFrame:
    files = [REPO_ROOT / "backend" / "data" / "raw" / "nasa_power_bengaluru_daily_2015_2024.json"]
    files += sorted(weather_dir().glob("*.json"))
    frames = [_load_one(p) for p in files if p.exists()]
    if not frames:
        raise FileNotFoundError("No NASA POWER files found")
    df = pd.concat(frames)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index.name = "date"
    return df


def build_weekly_weather() -> pd.DataFrame:
    daily = load_daily()
    wk = pd.DataFrame({
        "rain_mm": daily["PRECTOTCORR"].resample("W-SUN").sum(min_count=4),
        "rain_days": (daily["PRECTOTCORR"] >= 2.5).resample("W-SUN").sum(),   # IMD "rainy day" threshold
        "temp_mean_c": daily["T2M"].resample("W-SUN").mean(),
        "temp_max_c": daily["T2M_MAX"].resample("W-SUN").mean(),
        "temp_min_c": daily["T2M_MIN"].resample("W-SUN").mean(),
        "rh_mean_pct": daily["RH2M"].resample("W-SUN").mean(),
        "n_days": daily["T2M"].resample("W-SUN").count(),
    })
    wk.index.name = "week_end"
    return wk.reset_index()
