"""Ward-level risk ESTIMATES from the city-level forecast, with uncertainty.

There is no public ward-level dengue data, so ward numbers are a model, not observations:

  expected_cases_i = city_forecast x share_i,     share_i ∝ population_i x relative_risk_i

  * population_i: the 2023 ward polygons don't match the 2011 census wards, so population is
    estimated by area x (inverse-distance-weighted density from the 2011 ward centroids),
    rescaled to the census total.
  * relative_risk_i = (density_i / median)^beta x report_factor_i
      - beta (default 0.3) is a mild, configurable PRIOR that denser wards carry more risk;
      - report_factor_i is an empirical-Bayes multiplier from verified breeding-spot reports in the
        last 4 weeks (shrunk towards 1 when there are few reports).
  * Uncertainty = city forecast uncertainty x allocation uncertainty (Dirichlet draws),
    simulated by Monte Carlo. The map shows the interval width so the estimate never looks
    more precise than it is.
Pure numpy (no GIS dependencies), so it runs anywhere.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

EARTH_R_KM = 6371.0088
# Default bands (weekly reported cases per 100k). publish.py replaces these with bands derived from
# the city's own history (median / 75th / 90th percentile weeks), so "high" means high *for Bengaluru*.
BANDS = [(0.0, "low"), (2.0, "moderate"), (5.0, "high"), (10.0, "very_high")]


def bands_from_history(weekly_rates: np.ndarray) -> list[tuple[float, str]]:
    r = np.asarray(weekly_rates, float)
    r = r[~np.isnan(r)]
    if len(r) < 20:
        return BANDS
    q50, q75, q90 = np.quantile(r, [0.5, 0.75, 0.9])
    return [(0.0, "low"), (round(float(q50), 2), "moderate"), (round(float(q75), 2), "high"), (round(float(q90), 2), "very_high")]


# ------------------------------------------------------------------ geometry helpers
def _rings(geom: dict) -> list[list[list[float]]]:
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [poly[0] for poly in geom["coordinates"]]
    return []


def ring_area_centroid(ring: list[list[float]], lat0: float) -> tuple[float, float, float]:
    """Area (km²) and centroid (lon, lat) of a lon/lat ring via local equirectangular projection."""
    pts = np.asarray(ring, float)[:, :2]
    kx = math.cos(math.radians(lat0)) * math.pi / 180 * EARTH_R_KM
    ky = math.pi / 180 * EARTH_R_KM
    x, y = pts[:, 0] * kx, pts[:, 1] * ky
    cross = x[:-1] * y[1:] - x[1:] * y[:-1]
    a = cross.sum() / 2
    if abs(a) < 1e-12:
        return 0.0, float(pts[:, 0].mean()), float(pts[:, 1].mean())
    cx = ((x[:-1] + x[1:]) * cross).sum() / (6 * a)
    cy = ((y[:-1] + y[1:]) * cross).sum() / (6 * a)
    return abs(a), cx / kx, cy / ky


def point_in_ring(lon: float, lat: float, ring: list[list[float]]) -> bool:
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > lat) != (y2 > lat):
            xin = (x2 - x1) * (lat - y1) / (y2 - y1 + 1e-15) + x1
            if lon < xin:
                inside = not inside
    return inside


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R_KM * np.arcsin(np.sqrt(a))


# ------------------------------------------------------------------ ward table
def load_wards(geojson_path: Path, name_key: str = "KGISWardName", id_key: str = "KGISWardNo") -> pd.DataFrame:
    gj = json.loads(Path(geojson_path).read_text())
    rows = []
    for f in gj["features"]:
        rings = _rings(f["geometry"])
        if not rings:
            continue
        lat0 = float(np.mean([p[1] for p in rings[0]]))
        parts = [ring_area_centroid(r, lat0) for r in rings]
        area = sum(p[0] for p in parts)
        cx = sum(p[0] * p[1] for p in parts) / area if area else parts[0][1]
        cy = sum(p[0] * p[2] for p in parts) / area if area else parts[0][2]
        rows.append({"ward_id": str(f["properties"].get(id_key)), "ward_name": f["properties"].get(name_key),
                     "area_km2": area, "lon": cx, "lat": cy})
    return pd.DataFrame(rows)


def estimate_population(wards: pd.DataFrame, census: pd.DataFrame, k: int = 4) -> pd.DataFrame:
    """census: columns lat, lng, population, population_density (2011 wards)."""
    clat, clon = census["lat"].values, census["lng"].values
    dens = census["population_density"].values
    est = []
    for _, w in wards.iterrows():
        d = haversine_km(w["lat"], w["lon"], clat, clon)
        idx = np.argsort(d)[:k]
        wts = 1 / np.maximum(d[idx], 0.2) ** 2
        est.append(float((dens[idx] * wts).sum() / wts.sum()))
    out = wards.copy()
    out["density_est"] = est
    raw = out["density_est"] * out["area_km2"]
    out["population_est"] = raw * census["population"].sum() / raw.sum()
    out["population_method"] = "IDW density from 2011 census ward centroids x 2023 ward area, scaled to census total"
    return out


def ward_of_point(lat: float, lon: float, features: list[dict], id_key: str = "KGISWardNo") -> str | None:
    for f in features:
        if any(point_in_ring(lon, lat, r) for r in _rings(f["geometry"])):
            return str(f["properties"].get(id_key))
    return None


# ------------------------------------------------------------------ allocation
def band_for(rate_per_100k: float, bands=None) -> str:
    bands = bands or BANDS
    label = bands[0][1]
    for threshold, name in bands:
        if rate_per_100k >= threshold:
            label = name
    return label


def allocate(wards: pd.DataFrame, city_forecast: dict, beta: float = 0.3, reports: pd.Series | None = None,
             report_prior: float = 3.0, concentration: float = 400.0, n_sims: int = 500, seed: int = 0,
             bands=None) -> pd.DataFrame:
    """city_forecast: {"median", "lo80", "hi80", ...} for one horizon. reports: verified reports per ward_id."""
    rng = np.random.default_rng(seed)
    pop = wards["population_est"].values
    rr = (wards["density_est"].values / np.median(wards["density_est"].values)) ** beta
    if reports is not None and reports.sum() > 0:
        obs = wards["ward_id"].map(reports).fillna(0).values
        expected = reports.sum() * pop / pop.sum()
        rr = rr * (obs + report_prior) / (expected + report_prior)  # empirical Bayes, shrunk to 1
    share = pop * rr / (pop * rr).sum()

    med = city_forecast["median"]
    lo, hi = city_forecast.get("lo80", med), city_forecast.get("hi80", med)
    # Lognormal for the city total matched to the 80% interval (z = 1.2816).
    sigma = max((math.log1p(hi) - math.log1p(lo)) / (2 * 1.2816), 1e-6)
    city_draws = np.expm1(rng.normal(math.log1p(med), sigma, n_sims)).clip(min=0)
    share_draws = rng.dirichlet(share * concentration + 1e-6, n_sims)
    cases = share_draws * city_draws[:, None]
    rate = cases / pop[None, :] * 1e5

    out = wards[["ward_id", "ward_name", "population_est", "lat", "lon"]].copy()
    out["expected_cases"] = np.median(cases, axis=0).round(2)
    out["cases_lo80"] = np.quantile(cases, 0.1, axis=0).round(2)
    out["cases_hi80"] = np.quantile(cases, 0.9, axis=0).round(2)
    out["rate_per_100k"] = np.median(rate, axis=0).round(2)
    out["rate_lo80"] = np.quantile(rate, 0.1, axis=0).round(2)
    out["rate_hi80"] = np.quantile(rate, 0.9, axis=0).round(2)
    bands = bands or BANDS
    out["band"] = [band_for(r, bands) for r in out["rate_per_100k"]]
    # Probability the ward is in the high or very high band: lets the UI say "likely" vs "possibly".
    out["p_high"] = (rate >= bands[2][0]).mean(axis=0).round(3)
    width = (out["rate_hi80"] - out["rate_lo80"]) / out["rate_per_100k"].clip(lower=1e-6)
    out["uncertainty"] = np.select([width < 0.5, width < 1.0], ["low", "medium"], default="high")
    out["relative_risk"] = rr.round(3)
    return out
