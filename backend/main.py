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
    """Basic liveness probe."""
    return JSONResponse({"status": "ok", "app": settings.app_name, "env": settings.app_env})


@app.get("/health/db", tags=["system"])
async def db_health_check():
    """Readiness probe specifically for database connectivity."""
    try:
        from db.client import get_supabase
        sb = get_supabase()
        result = sb.table("wards").select("id", count="exact").limit(1).execute()
        count = result.count if result.count is not None else len(result.data)
        return JSONResponse({"status": "ok", "wards_in_db": count})
    except Exception as e:
        logger.error("DB health check failed: %s", e)
        return JSONResponse({"status": "error", "detail": str(e)}, status_code=503)


@app.get("/health/detailed", tags=["system"])
async def detailed_health_check():
    """
    Comprehensive subsystem health check distinguishing:
    - Application process
    - Database connection
    - Dengue ML model weights
    - Acoustic & Skin health screening models
    - External AI API configuration
    """
    from pathlib import Path
    models_dir = Path(__file__).parent / "ml" / "model"
    health_models_dir = Path(__file__).parent / "healthcheck" / "models"

    subsystems = {
        "api": "healthy",
        "database": "unknown",
        "dengue_ml_model": "available" if (models_dir / "xgb_dengue.pkl").exists() else "missing",
        "skin_dl_model": "available" if (health_models_dir / "skin_model" / "model.safetensors").exists() else "missing",
        "cough_dl_model": "available" if (health_models_dir / "cough_model" / "model.safetensors").exists() else "missing",
        "ai_openrouter": "configured" if bool(settings.openrouter_api_key) else "unconfigured",
        "weather_api": "configured" if bool(settings.openweathermap_api_key) else "unconfigured",
    }

    status_code = 200
    try:
        from db.client import get_supabase
        sb = get_supabase()
        res = sb.table("wards").select("id", count="exact").limit(1).execute()
        subsystems["database"] = "connected"
    except Exception as e:
        subsystems["database"] = f"unreachable: {str(e)}"
        status_code = 503

    overall_status = "operational" if status_code == 200 else "degraded"
    return JSONResponse(
        {
            "status": overall_status,
            "app": settings.app_name,
            "environment": settings.app_env,
            "subsystems": subsystems,
        },
        status_code=status_code,
    )


@app.on_event("startup")
async def on_startup():
    logger.info("NeighborHealth backend starting [env=%s]", settings.app_env)

