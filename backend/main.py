import uuid
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from utils.logger import get_logger, request_id_var
from api import risk, wards, reports, subscriptions, chat, users
from api.ml_info import router as ml_router
from healthcheck.routes import router as health_router

settings = get_settings()
logger = get_logger("API")

import logging
logging.getLogger("uvicorn.access").handlers = []
logging.getLogger("uvicorn.error").propagate = False
logging.getLogger("fastapi").propagate = False

app = FastAPI(
    title=settings.app_name,
    description="Hyperlocal disease prediction and early-warning system for Bengaluru.",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    req_id = uuid.uuid4().hex[:6]
    token = request_id_var.set(req_id)
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
        duration = (time.perf_counter() - start_time) * 1000
        logger.info(f"{request.method} {request.url.path} - {response.status_code} ({duration:.1f}ms)")
        return response
    except Exception as e:
        duration = (time.perf_counter() - start_time) * 1000
        logger.error(f"{request.method} {request.url.path} -> Failed: {str(e)} ({duration:.1f}ms)")
        raise
    finally:
        request_id_var.reset(token)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(risk.router,          prefix="/api/v1")
app.include_router(wards.router,         prefix="/api/v1")
app.include_router(reports.router,       prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(chat.router,          prefix="/api/v1")
app.include_router(users.router,         prefix="/api/v1")
app.include_router(ml_router,            prefix="/api/v1")
app.include_router(health_router,        prefix="/api/health")

@app.get("/health", tags=["system"])
async def health_check():
    return JSONResponse({"status": "ok", "app": settings.app_name, "env": settings.app_env})

@app.get("/health/db", tags=["system"])
async def db_health_check():
    try:
        from db.client import get_supabase
        sb = get_supabase()
        result = sb.table("wards").select("id", count="exact").execute()
        count = result.count if result.count is not None else len(result.data)
        return JSONResponse({"status": "ok", "wards_in_db": count})
    except Exception as e:
        logger.error("DB health check failed: %s", e)
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)

@app.on_event("startup")
async def on_startup():
    logger.info("NeighborHealth backend starting [env=%s]", settings.app_env)
