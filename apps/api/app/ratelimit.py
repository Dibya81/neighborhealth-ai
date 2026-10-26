"""In-process sliding-window rate limiter (per key). Good enough for one API instance; with several
instances behind a load balancer, move the counters to Redis."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

from app.security import client_ip

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def limit(name: str, max_calls: int, per_seconds: int):
    def dep(request: Request) -> None:
        key = f"{name}:{client_ip(request)}"
        now = time.monotonic()
        with _lock:
            q = _hits[key]
            while q and now - q[0] > per_seconds:
                q.popleft()
            if len(q) >= max_calls:
                raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests, please slow down")
            q.append(now)
    return dep
