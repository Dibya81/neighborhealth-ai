from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from utils.logger import get_logger

logger = get_logger(__name__)

# In-memory store: ip_hash -> list of request timestamps
# Sufficient for hackathon scale. Replace with Redis for production.
_request_log: dict[str, list[datetime]] = defaultdict(list)


def get_client_ip(request: Request) -> str:
    """Extracts real IP, respecting Railway/Vercel reverse proxy headers."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(max_requests: int = 3, window_minutes: int = 60):
    """
    Returns a FastAPI dependency that enforces IP-based rate limiting.

    Usage on any endpoint:
        @router.post("/reports")
        async def submit_report(
            request: Request,
            _: None = Depends(rate_limit(max_requests=3, window_minutes=60))
        ):
            ...
    """
    async def _check(request: Request):
        ip = get_client_ip(request)
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)

        # Prune old timestamps outside the window
        _request_log[ip] = [
            ts for ts in _request_log[ip] if ts > window_start
        ]

        if len(_request_log[ip]) >= max_requests:
            logger.warning("Rate limit hit for IP %s", ip)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many requests. Max {max_requests} per {window_minutes} minutes.",
            )

        _request_log[ip].append(now)

    return _check
