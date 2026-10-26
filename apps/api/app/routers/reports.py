from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from app import db
from app.ratelimit import limit
from app.security import current_user
from app.services.hotspots import detect_hotspots
from app.services.reports import ReportRejected, create_report, public_report, trust_score
from app.settings import get_settings

router = APIRouter(prefix="/v2", tags=["reports"])


@router.post("/reports", dependencies=[Depends(limit("reports", 20, 3600))])
async def submit_report(lat: float = Form(...), lon: float = Form(...), category: str = Form(...),
                        description: str | None = Form(None), photo: UploadFile = File(...),
                        user: dict = Depends(current_user)):
    data = await photo.read()
    try:
        res = create_report(user, lat, lon, category, description, data, photo.filename or "photo.jpg")
    except ReportRejected as e:
        raise HTTPException(422, str(e))
    r = res.report
    messages = {
        "duplicate": "Thanks! Someone already reported this spot, so we've linked your report to it.",
        "spam": "We couldn't accept this photo. Please send a clear photo of standing water or a container.",
        "pending": "Thank you! Your report will be reviewed by the health team.",
    }
    return {"id": r["id"], "status": r["status"], "ward_id": r["ward_id"], "vision": r["vision_label"],
            "message": messages.get(r["status"], "Received")}


@router.get("/reports/mine")
def my_reports(user: dict = Depends(current_user)):
    rows = db.fetchall("SELECT id, lat, lon, ward_id, category, status, vision_label, created_at, reviewed_at "
                       "FROM reports WHERE user_id = ? ORDER BY created_at DESC LIMIT 100", (user["id"],))
    return {"reports": rows, "trust": trust_score(user["id"])}


@router.get("/reports/public")
def public_reports(days: int = Query(28, ge=1, le=90)):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.fetchall("SELECT * FROM reports WHERE created_at >= ? AND status IN ('verified', 'pending')", (since,))
    return {"reports": [public_report(r) for r in rows]}


@router.get("/hotspots")
def hotspots(days: int | None = Query(None, ge=1, le=90)):
    return {"hotspots": [{k: v for k, v in h.items() if k != "report_ids"} for h in detect_hotspots(days)]}


@router.get("/reports/{report_id}/photo")
def report_photo(report_id: str, user: dict = Depends(current_user)):
    r = db.fetchone("SELECT user_id, photo_path FROM reports WHERE id = ?", (report_id,))
    if not r:
        raise HTTPException(404, "Not found")
    if r["user_id"] != user["id"] and user["role"] not in ("official", "admin"):
        raise HTTPException(403, "Not allowed")
    path = get_settings().upload_dir / "reports" / r["photo_path"]
    if not path.exists():
        raise HTTPException(404, "Photo missing")
    return FileResponse(path, media_type="image/jpeg")
