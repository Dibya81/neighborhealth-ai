import time
from typing import Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)


class InMemoryCache:
    """
    Simple TTL-based in-memory cache.
    Used for:
    - GET /risk/all  (TTL: 1 hour — refreshed by daily pipeline)
    - GET /wards     (TTL: 24 hours — static data)

    Replace with Redis for multi-worker production deployments.
    For Railway with a single worker, this is sufficient.
    """

    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        value, expires_at = self._store[key]
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self._store[key] = (value, time.time() + ttl_seconds)
        logger.debug("Cache SET key=%s ttl=%ds", key, ttl_seconds)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()
        logger.info("Cache cleared")


# Module-level singleton — import this anywhere
cache = InMemoryCache()
