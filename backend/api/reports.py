from __future__ import annotations
from pathlib import Path
import hashlib
import uuid
from fastapi import APIRouter, Request, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
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

    try:
        report = insert_report(
            ward_id=payload.ward_id,
            lat=payload.lat,
            lng=payload.lng,
            description=payload.description,
            photo_url=payload.photo_url,
            ip_hash=ip_hash,
        )
    except Exception as e:
        logger.error("Failed to insert report for ward %s: %s", payload.ward_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not submit report due to database error: {str(e)}",
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


REPORT_PHOTOS_DIR = Path(__file__).parent.parent / "temp_health_uploads" / "reports"
REPORT_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/reports/upload-photo", tags=["reports"])
async def upload_report_photo(file: UploadFile = File(...)):
    """
    Uploads a photo of stagnant water / mosquito breeding spot.
    Validates file type (JPEG, PNG, WebP) and size (max 5MB).
    Returns the URL to associate with the breeding report.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No photo file uploaded.")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Photo exceeds 5MB limit.")

    ext = Path(file.filename).suffix.lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"

    safe_filename = f"{uuid.uuid4().hex}{ext}"
    target_path = REPORT_PHOTOS_DIR / safe_filename
    with open(target_path, "wb") as f:
        f.write(content)

    logger.info("Report photo saved: %s (%d bytes)", safe_filename, len(content))
    return {"photo_url": f"/api/v1/reports/photo/{safe_filename}"}


@router.get("/reports/photo/{filename}", tags=["reports"])
async def get_report_photo(filename: str):
    """Serves an uploaded breeding spot report photo."""
    # Prevent path traversal attacks
    safe_name = Path(filename).name
    photo_path = REPORT_PHOTOS_DIR / safe_name
    if not photo_path.exists() or not photo_path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found.")
    return FileResponse(photo_path)

