"""NeighborHealth 2.0 API.

    cd apps/api && uvicorn app.main:app --reload --port 8000
    docs: http://localhost:8000/docs
"""
from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, Response

from app import db
from app.forecast_store import freshness_days, get_bundle
from app.routers import alerts, assistant, auth, officials, public, reports
from app.settings import get_settings

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
    REQS = Counter("nh_http_requests_total", "HTTP requests", ["method", "route", "status"])
    LAT = Histogram("nh_http_request_seconds", "Request latency", ["route"],
                    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5))
    FRESH = Gauge("nh_forecast_age_days", "Age of the published forecast in days")
except ImportError:  # metrics are optional in development
    REQS = LAT = FRESH = None


class JsonFormatter(logging.Formatter):
    def format(self, r: logging.LogRecord) -> str:
        base = {"t": self.formatTime(r), "level": r.levelname, "logger": r.name, "msg": r.getMessage()}
        base.update(getattr(r, "extra_fields", {}))
        return json.dumps(base)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
log = logging.getLogger("api")

settings = get_settings()
if settings.sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1, environment=settings.env)
    except ImportError:
        pass

app = FastAPI(title="NeighborHealth API", version="2.0.0",
              description="Dengue early warning for Bengaluru: forecasts, reports, alerts, officials' tools.")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def observe(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error", extra={"extra_fields": {"request_id": rid, "path": request.url.path}})
        response = JSONResponse({"detail": "Internal error", "request_id": rid}, status_code=500)
    elapsed = time.perf_counter() - start
    route = request.scope.get("route")
    path = getattr(route, "path", "unmatched")
    if REQS:
        REQS.labels(request.method, path, response.status_code).inc()
        LAT.labels(path).observe(elapsed)
    response.headers["x-request-id"] = rid
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
    if elapsed > 1.0:
        log.info("slow request", extra={"extra_fields": {"path": path, "ms": round(elapsed * 1000), "request_id": rid}})
    return response


@app.on_event("startup")
def startup() -> None:
    applied = db.migrate()
    if applied:
        log.info(f"applied migrations: {applied}")
    if not get_bundle():
        log.warning("no forecast bundle found; run `python -m ml weekly` to publish one")


@app.get("/health", tags=["ops"])
def health():
    age = freshness_days()
    try:
        db.fetchone("SELECT 1 AS ok")
        db_ok = True
    except Exception:
        db_ok = False
    status = "ok" if db_ok and age is not None and age < 10 else "degraded"
    return {"status": status, "db": db_ok, "forecast_age_days": round(age, 2) if age is not None else None}


@app.get("/metrics", include_in_schema=False)
def metrics():
    if not REQS:
        return Response("prometheus_client not installed", status_code=501)
    age = freshness_days()
    if age is not None:
        FRESH.set(age)
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


for r in (auth.router, public.router, reports.router, officials.router, alerts.router, assistant.router):
    app.include_router(r)
