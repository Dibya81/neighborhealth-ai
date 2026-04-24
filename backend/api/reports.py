from __future__ import annotations
import hashlib
from fastapi import APIRouter, Request, Depends, HTTPException, status
from models.report import ReportCreate, ReportResponse, ReportItem
from db.reports import insert_report, get_reports_for_ward
from db.wards import ward_exists
from utils.rate_limiter import rate_limit, get_client_ip
from utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["reports"],
    dependencies=[Depends(rate_limit(max_requests=3, window_minutes=60))],
)
async def submit_report(payload: ReportCreate, request: Request):
    """
    Submit a mosquito breeding spot report.
    Rate-limited: 3 reports per IP per hour.
    The report feeds into the next morning's risk calculation.
    """
    if not ward_exists(payload.ward_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ward {payload.ward_id} not found.",
        )

    # Hash the IP for spam detection — never store raw IP
    ip = get_client_ip(request)
    ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]

    report = insert_report(
        ward_id=payload.ward_id,
        lat=payload.lat,
        lng=payload.lng,
        description=payload.description,
        photo_url=payload.photo_url,
        ip_hash=ip_hash,
    )

    logger.info("Report submitted: ward=%s id=%s", payload.ward_id, report["id"])
    return ReportResponse(
        id=report["id"],
        status="received",
        message="Report received. It will be included in tomorrow's risk update.",
    )


@router.get("/reports/ward/{ward_id}", response_model=list[ReportItem], tags=["reports"])
async def get_ward_reports(ward_id: str, days: int = 7):
    """
    Returns recent non-spam reports for a ward.
    Shown in the ward detail panel on the map.
    """
    reports = get_reports_for_ward(ward_id, days=days)
    return [
        ReportItem(
            id=r["id"],
            lat=r["lat"],
            lng=r["lng"],
            description=r.get("description"),
            photo_url=r.get("photo_url"),
            status=r["status"],
            reported_at=str(r["reported_at"]),
        )
        for r in reports
    ]
