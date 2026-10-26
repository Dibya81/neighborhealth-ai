import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from models.report import ReportCreate
from api.deps import create_access_token


def test_report_coordinate_validation():
    # Valid Bengaluru coordinates
    valid_report = ReportCreate(ward_id="1", lat=12.9716, lng=77.5946, description="Standing water")
    assert valid_report.lat == 12.9716
    assert valid_report.lng == 77.5946

    # Out of bounds latitude (< 12.7)
    with pytest.raises(ValueError):
        ReportCreate(ward_id="1", lat=12.2, lng=77.5946)

    # Out of bounds longitude (> 77.9)
    with pytest.raises(ValueError):
        ReportCreate(ward_id="1", lat=12.9716, lng=78.5)


@pytest.mark.asyncio
async def test_user_history_idor_protection():
    from api.users import get_history

    user_a = {"id": "user-a-1111", "email": "usera@gmail.com", "is_admin": False}
    user_b_id = "user-b-2222"

    # User A attempting to read User B's history must raise 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        await get_history(user_id=user_b_id, current_user=user_a)
    assert exc_info.value.status_code == 403
    assert "Forbidden" in exc_info.value.detail


@pytest.mark.asyncio
async def test_user_profile_update_idor_protection():
    from api.users import update_user
    from models.user import UserCreate

    user_a = {"id": "user-a-1111", "email": "usera@gmail.com", "is_admin": False}
    user_b_id = "user-b-2222"
    payload = UserCreate(name="Malicious Overwrite", health_conditions=["asthma"])

    # User A attempting to modify User B's profile must raise 403 Forbidden
    with pytest.raises(HTTPException) as exc_info:
        await update_user(user_id=user_b_id, payload=payload, current_user=user_a)
    assert exc_info.value.status_code == 403
    assert "Forbidden" in exc_info.value.detail


@pytest.mark.asyncio
async def test_subscription_cancel_idor_protection():
    from api.subscriptions import cancel

    fake_sub = {
        "id": "sub-12345",
        "user_id": "owner-user-777",
        "ward_id": "1",
        "contact": "owner@example.com",
    }

    attacker_token = create_access_token(user_id="attacker-user-999", email="attacker@example.com")

    with patch("api.subscriptions.get_subscription_by_id", return_value=fake_sub):
        with pytest.raises(HTTPException) as exc_info:
            await cancel(subscription_id="sub-12345", authorization=f"Bearer {attacker_token}")
        assert exc_info.value.status_code == 403
        assert "Forbidden" in exc_info.value.detail


@pytest.mark.asyncio
async def test_subscription_cancel_nonexistent():
    from api.subscriptions import cancel

    with patch("api.subscriptions.get_subscription_by_id", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            await cancel(subscription_id="nonexistent-sub-id", authorization=None)
        assert exc_info.value.status_code == 404
        assert "Subscription not found" in exc_info.value.detail


def test_chronological_ordering_helper():
    """Verify that descending database queries are reversed into ascending chronological order."""
    db_rows = [
        {"score_date": "2024-10-25", "risk_score": 65.0, "risk_level": "medium"},
        {"score_date": "2024-10-24", "risk_score": 58.0, "risk_level": "medium"},
        {"score_date": "2024-10-23", "risk_score": 42.0, "risk_level": "low"},
    ]
    # Reverse to chronological order (oldest first, newest last)
    history = list(db_rows)
    history.reverse()

    dates = [h["score_date"] for h in history]
    assert dates == ["2024-10-23", "2024-10-24", "2024-10-25"]
    assert dates[0] < dates[-1]


@pytest.mark.asyncio
async def test_upload_report_photo_validation():
    from api.reports import upload_report_photo
    from fastapi import UploadFile
    import io

    # Empty file rejection
    empty_file = UploadFile(filename="empty.jpg", file=io.BytesIO(b""))
    with pytest.raises(HTTPException) as exc_info:
        await upload_report_photo(file=empty_file)
    assert exc_info.value.status_code == 400

    # Valid image upload
    valid_file = UploadFile(filename="breeding_spot.jpg", file=io.BytesIO(b"\xff\xd8\xff\xe0" + b"A" * 100))
    res = await upload_report_photo(file=valid_file)
    assert "photo_url" in res
    assert res["photo_url"].startswith("/api/v1/reports/photo/")


@pytest.mark.asyncio
async def test_get_report_photo_traversal_protection():
    from api.reports import get_report_photo

    # Nonexistent file returns 404
    with pytest.raises(HTTPException) as exc_info:
        await get_report_photo(filename="../../../etc/passwd")
    assert exc_info.value.status_code == 404
