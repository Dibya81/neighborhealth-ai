from fastapi import Header, HTTPException, status
from config import get_settings

settings = get_settings()


async def verify_admin_key(x_admin_key: str = Header(...)):
    """
    Dependency for admin-only endpoints.
    Validates the x-admin-key header against ADMIN_API_KEY env var.

    Usage:
        @router.post("/admin/trigger-refresh")
        async def trigger_refresh(_: None = Depends(verify_admin_key)):
            ...
    """
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key.",
        )
