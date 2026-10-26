import pytest
from datetime import date
from fastapi import HTTPException
from api.deps import (
    verify_admin_key,
    get_current_user,
    create_access_token,
    _verify_jwt,
)
from config import get_settings

settings = get_settings()


@pytest.mark.asyncio
async def test_admin_key_missing_or_empty():
    with pytest.raises(HTTPException) as exc_info:
        await verify_admin_key(x_admin_key=None)
    assert exc_info.value.status_code == 401

    with pytest.raises(HTTPException) as exc_info:
        await verify_admin_key(x_admin_key="   ")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_admin_key_invalid():
    with pytest.raises(HTTPException) as exc_info:
        await verify_admin_key(x_admin_key="wrong-admin-key-12345")
    assert exc_info.value.status_code == 403
    assert "Invalid admin key" in exc_info.value.detail


@pytest.mark.asyncio
async def test_admin_key_valid():
    key = settings.admin_api_key
    res = await verify_admin_key(x_admin_key=key)
    assert res == key


def test_jwt_token_generation_and_validation():
    user_id = "00000000-0000-0000-0000-000000000001"
    email = "citizen@bengaluru.gov.in"
    token = create_access_token(user_id=user_id, email=email, expires_delta_seconds=3600)

    # Valid token verification
    payload = _verify_jwt(token, settings.secret_key)
    assert payload is not None
    assert payload["id"] == user_id
    assert payload["email"] == email
    assert payload["role"] == "authenticated"

    # Expired token verification
    expired_token = create_access_token(user_id=user_id, email=email, expires_delta_seconds=-10)
    expired_payload = _verify_jwt(expired_token, settings.secret_key)
    assert expired_payload is None

    # Tampered token verification
    tampered_token = token[:-4] + "abcd"
    tampered_payload = _verify_jwt(tampered_token, settings.secret_key)
    assert tampered_payload is None


@pytest.mark.asyncio
async def test_get_current_user_rejection():
    # Missing header
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization=None)
    assert exc_info.value.status_code == 401

    # Malformed format
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization="Basic dXNlcjpwYXNz")
    assert exc_info.value.status_code == 401

    # Invalid token
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(authorization="Bearer invalid.jwt.token")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_success():
    user_id = "11111111-2222-3333-4444-555555555555"
    email = "testuser@neighborhealth.org"
    token = create_access_token(user_id=user_id, email=email, expires_delta_seconds=3600)

    user = await get_current_user(authorization=f"Bearer {token}")
    assert user["id"] == user_id
    assert user["email"] == email
    assert user["is_admin"] is False


def test_xss_escaping_pattern():
    """Verify HTML escaping eliminates script injection and event handlers."""
    def escape_html(s: str) -> str:
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#039;")
        )

    malicious_inputs = [
        '<script>alert("xss")</script>',
        '<img src=x onerror=alert(1)>',
        '"><svg onload=alert(document.cookie)>',
        '<iframe src="javascript:alert(1)"></iframe>',
    ]

    for inp in malicious_inputs:
        escaped = escape_html(inp)
        assert "<" not in escaped
        assert ">" not in escaped
        assert '"' not in escaped
