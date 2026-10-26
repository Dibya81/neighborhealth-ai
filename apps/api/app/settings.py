"""All configuration comes from environment variables (12-factor). See apps/api/.env.example."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app import REPO_ROOT


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    env: str = os.environ.get("APP_ENV", "development")
    city: str = os.environ.get("NH_CITY", "bengaluru")
    database_url: str = os.environ.get("DATABASE_URL", f"sqlite:///{REPO_ROOT / 'data' / 'v2' / 'app.db'}")
    redis_url: str | None = os.environ.get("REDIS_URL") or None
    jwt_secret: str = os.environ.get("JWT_SECRET", "dev-only-change-me")
    public_api_url: str = os.environ.get("PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    jwt_ttl_hours: int = int(os.environ.get("JWT_TTL_HOURS", "72"))
    allowed_origins: list[str] = field(default_factory=lambda: [
        o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()])
    upload_dir: Path = Path(os.environ.get("UPLOAD_DIR", str(REPO_ROOT / "data" / "v2" / "uploads")))
    max_upload_mb: int = int(os.environ.get("MAX_UPLOAD_MB", "8"))
    public_web_url: str = os.environ.get("PUBLIC_WEB_URL", "http://localhost:3000")

    openrouter_api_key: str | None = os.environ.get("OPENROUTER_API_KEY") or None
    llm_model: str = os.environ.get("NH_LLM_MODEL", "google/gemini-2.0-flash-001")

    twilio_sid: str | None = os.environ.get("TWILIO_ACCOUNT_SID") or None
    twilio_token: str | None = os.environ.get("TWILIO_AUTH_TOKEN") or None
    twilio_sms_from: str | None = os.environ.get("TWILIO_FROM_NUMBER") or None
    twilio_whatsapp_from: str | None = os.environ.get("TWILIO_WHATSAPP_FROM") or None
    smtp_host: str = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port: int = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user: str | None = os.environ.get("SMTP_USER") or os.environ.get("GMAIL_USER") or None
    smtp_password: str | None = os.environ.get("SMTP_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD") or None
    alerts_dry_run: bool = _bool("ALERTS_DRY_RUN", True)   # log instead of sending until you switch it off

    vision_enabled: bool = _bool("VISION_ENABLED", False)
    sentry_dsn: str | None = os.environ.get("SENTRY_DSN") or None

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith(("postgres://", "postgresql://"))


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.env == "production" and s.jwt_secret == "dev-only-change-me":
        raise RuntimeError("Set JWT_SECRET in production")
    s.upload_dir.mkdir(parents=True, exist_ok=True)
    return s
