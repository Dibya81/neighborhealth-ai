from __future__ import annotations
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: str = "development"
    app_name: str = "NeighborHealth"
    secret_key: str = "dev-secret-key-change-in-production"
    admin_api_key: str = "dev-admin-key-change-in-production"

    # Supabase
    supabase_url: str
    supabase_key: str = ""
    supabase_service_role_key: str

    # OpenWeatherMap
    openweathermap_api_key: str = ""

    # Groq
    groq_api_key: str = ""

    # xAI Grok
    xai_api_key: str = ""

    # Firebase
    firebase_service_account_path: str = ""

    # Gmail SMTP
    gmail_user: str = ""
    gmail_app_password: str = ""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # CORS — parsed from comma-separated string
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://[::1]:3000"

    # Bengaluru coordinates
    bengaluru_lat: float = 12.9716
    bengaluru_lon: float = 77.5946

    # Alert config
    alert_threshold: int = 70

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache()
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    Use this everywhere — never instantiate Settings() directly.

    Usage:
        from config import get_settings
        settings = get_settings()
    """
    return Settings()
