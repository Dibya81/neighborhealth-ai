import pandas as pd
from datetime import date


WARD_DENSITIES = [
    8500,9200,7800,6900,12000,9800,10200,7200,6500,8900,
    11500,10800,10100,8600,7400,7800,14500,9200,10600,13200,
    9800,7100,11900,15600,13800,12200,10500,9200,8100,8600,
    13100,11800,7900,12400,11200,10800,11500,15200,14600,10900,
    13400,14100,11800,10400,9600,11200,12500,11800,18200,19800,
    15600,13200,14100,13500,16400,21500,17800,14200,12100,8900,
    9800,10900,11400,10200,8100,12600,13900,14200,12100,11400,
    12800,9600,10800,9200,10100,11900,14600,11200,9800,9100,
    8300,7600,13400,16800,13200,12400,11800,10200,9400,12600,
    17200,8800,11200,11800,13100,10600,20400,16200,17400,18800,
    14200,17600,12800,16400,15800,13200,12400,14600,13100,18400,
    17200,16800,15600,17400,16200,19600,18200,15800,13400,19200,
    16400,15200,17600,14800,16600,17800,14200,13100,14900,18600,
    20400,15800,17200,21800,14600,20200,18800,17400,19600,14400,
    13200,12400,11800,10200,16400,11800,9600,11200,9100,13200,
    11600,10400,9600,14800,12200,13600,13100,12400,13800,15600,
    13200,14800,12600,11200,17200,14400,16800,14600,13200,12800,
    13400,16200,17400,13800,14200,16400,12600,11800,13900,17600,
    14200,13400,11600,17800,13200,12400,11200,10400,11800,10900,
    10200,11400,12800,12200,11600,13800,9800,9800,
]


def compute_rule_based_score(disease_id: str, weather: dict) -> float:
    month = date.today().month
    rain  = float(weather.get("rainfall_7d", 0))
    temp  = float(weather.get("temp_avg", 27))
    hum   = float(weather.get("humidity_avg", 65))

    if disease_id in ("heatstroke", "heat_exhaustion", "dehydration"):
        if temp < 30: return max(0.0, (temp - 25) * 4)
        if temp < 34: return 20.0 + (temp - 30) * 8
        return min(100.0, 52.0 + (temp - 34) * 12)

    if disease_id in ("cholera", "typhoid"):
        rain_score  = min(50.0, rain * 0.7)
        temp_score  = max(0.0, (temp - 22) * 2)
        month_boost = 15.0 if month in [6,7,8,9] else 0.0
        return min(100.0, rain_score + temp_score + month_boost)

    if disease_id == "hepatitis_a":
        rain_score  = min(60.0, rain * 0.8)
        month_boost = 20.0 if month in [7,8,9] else 0.0
        return min(100.0, rain_score + month_boost)

    if disease_id in ("common_cold", "bronchitis"):
        if temp > 25: return max(0.0, 30.0 - (temp - 25) * 4)
        return min(100.0, 30.0 + (25 - temp) * 5)

    if disease_id in ("allergic_rhinitis", "copd"):
        dry_score  = max(0.0, (70 - hum) * 0.8) if hum < 70 else 0.0
        cold_score = max(0.0, (24 - temp) * 3) if temp < 24 else 0.0
        return min(100.0, dry_score + cold_score + 15.0)

    return 30.0


def build_rule_based_ward_scores(base_score: float, ward_metadata: dict) -> pd.DataFrame:
    """
    Generates per-ward scores with meaningful density-based variation.
    Uses real ward density array to produce differentiated output.
    Range: base ± 25 points, ensuring visible map variation.
    """
    rows = []
    ward_ids = list(ward_metadata.keys())
    n = len(WARD_DENSITIES)

    all_densities = [
        ward_metadata[wid].get("population_density") or WARD_DENSITIES[i % n]
        for i, wid in enumerate(ward_ids)
    ]
    min_d = min(all_densities) if all_densities else 4200
    max_d = max(all_densities) if all_densities else 22000
    d_range = max(max_d - min_d, 1)

    for i, ward_id in enumerate(ward_ids):
        meta    = ward_metadata[ward_id]
        density = meta.get("population_density") or WARD_DENSITIES[i % n]

        # Normalise 0→1, then map to -20 → +25 range
        norm   = (density - min_d) / d_range
        offset = -20.0 + norm * 45.0

        # Deterministic per-ward noise (stable across runs)
        wid_int = 0
        for ch in str(ward_id):
            if ch.isdigit():
                wid_int = wid_int * 10 + int(ch)
        noise = ((wid_int * 7919) % 100) / 100.0 * 6.0 - 3.0

        final_score = min(100.0, max(0.0, base_score + offset + noise))

        rows.append({
            "ward_id":   ward_id,
            "risk_score": round(final_score, 2),
            "risk_level": _level(final_score),
        })

    return pd.DataFrame(rows)


def _level(score: float) -> str:
    if score < 40: return "low"
    if score < 70: return "medium"
    return "high"
