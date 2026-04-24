from integrations.weather import fetch_weather_with_db_cache
from utils.logger import get_logger

logger = get_logger(__name__)


def get_weather_features_for_pipeline() -> dict:
    return fetch_weather_with_db_cache()
