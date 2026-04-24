"""
OpenWeatherMap Integration
===========================
Fetches current + 5-day forecast for Bengaluru.
Returns weather_features dict including rainfall_lag14 approximation.
"""
import json
import urllib.request
import urllib.parse
from datetime import date
from config import get_settings
from utils.logger import get_logger

logger = get_logger(__name__)


def _owm_get(endpoint: str, params: dict) -> dict:
    settings = get_settings()
    params["appid"] = settings.openweathermap_api_key
    params["units"] = "metric"
    url = "https://api.openweathermap.org/data/2.5/" + endpoint + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read().decode())


def fetch_weather_features() -> dict:
    """
    Returns:
        rainfall_7d, rainfall_lag14, temp_avg, humidity_avg, consec_rain_days
    Falls back to seasonal defaults on API failure.
    """
    settings = get_settings()

    if not settings.openweathermap_api_key:
        logger.warning("OPENWEATHERMAP_API_KEY not set — using seasonal defaults")
        return _seasonal_defaults()

    try:
        data    = _owm_get("forecast", {"lat": settings.bengaluru_lat, "lon": settings.bengaluru_lon, "cnt": 40})
        entries = data.get("list", [])

        if not entries:
            return _seasonal_defaults()

        total_rain  = sum(e.get("rain", {}).get("3h", 0.0) for e in entries)
        temps       = [e["main"]["temp"] for e in entries]
        hums        = [e["main"]["humidity"] for e in entries]

        # Daily rain for consec_rain_days
        daily: dict[str, float] = {}
        for e in entries:
            day = e["dt_txt"][:10]
            daily[day] = daily.get(day, 0.0) + e.get("rain", {}).get("3h", 0.0)
        consec = 0
        for d in sorted(daily):
            if daily[d] > 2.0:
                consec += 1
            else:
                break

        rainfall_7d   = round(total_rain, 2)
        rainfall_lag14 = round(rainfall_7d * 1.8, 2)   # OWM free = 5 days max; approximate lag

        result = {
            "rainfall_7d":     rainfall_7d,
            "rainfall_lag14":  rainfall_lag14,
            "temp_avg":        round(sum(temps) / len(temps), 2),
            "humidity_avg":    round(sum(hums) / len(hums), 2),
            "consec_rain_days": consec,
        }
        logger.info(
            "OWM OK: rain7d=%.1fmm lag14=%.1fmm temp=%.1f°C hum=%.1f%%",
            result["rainfall_7d"], result["rainfall_lag14"],
            result["temp_avg"], result["humidity_avg"],
        )
        return result

    except Exception as e:
        logger.error("OWM fetch failed (%s) — seasonal defaults", e)
        return _seasonal_defaults()


def fetch_weather_with_db_cache() -> dict:
    """Caches in weather_cache table — one call per day."""
    from db.client import get_supabase
    sb    = get_supabase()
    today = date.today().isoformat()

    cached = (
        sb.table("weather_cache")
        .select("raw_payload")
        .eq("fetch_date", today)
        .limit(1)
        .execute()
    )
    if cached.data:
        logger.info("Weather cache HIT for %s", today)
        p = cached.data[0]["raw_payload"]
        # Ensure lag key exists for older cache entries
        if "rainfall_lag14" not in p:
            p["rainfall_lag14"] = round(p.get("rainfall_7d", 0) * 1.8, 2)
        return p

    data = fetch_weather_features()
    sb.table("weather_cache").upsert(
        {"fetch_date": today, "raw_payload": data},
        on_conflict="fetch_date",
    ).execute()
    logger.info("Weather cached for %s", today)
    return data


def _seasonal_defaults() -> dict:
    """Bengaluru seasonal baseline when API is unavailable."""
    from datetime import date as dt
    m = dt.today().month
    defaults = {
        1: (1.0, 1.8, 21.0, 52),  2: (2.0, 3.6, 24.0, 48),
        3: (8.0,14.4, 27.0, 43),  4:(25.0,45.0, 29.0, 50),
        5:(60.0,108., 27.5, 62),  6:(70.0,126., 24.5, 79),
        7:(80.0,144., 23.5, 82),  8:(95.0,171., 23.8, 83),
        9:(100.,180., 24.2, 81), 10:(95.0,171., 24.5, 78),
        11:(35.0,63., 22.8, 68), 12:(10.0,18., 21.0, 60),
    }
    r7, r14, t, h = defaults.get(m, (20.0, 36.0, 26.0, 65))
    return {
        "rainfall_7d":     r7,
        "rainfall_lag14":  r14,
        "temp_avg":        t,
        "humidity_avg":    float(h),
        "consec_rain_days": 0,
    }
