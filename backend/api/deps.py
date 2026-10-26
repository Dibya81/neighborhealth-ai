import hmac
import json
import base64
import time
from typing import Optional
from fastapi import Header, HTTPException, status, Depends
from config import get_settings
from utils.logger import get_logger

settings = get_settings()
logger = get_logger("AUTH")


def _decode_base64_url(val: str) -> bytes:
    """Decodes standard or url-safe base64 with padding."""
    rem = len(val) % 4
    if rem > 0:
        val += "=" * (4 - rem)
    return base64.urlsafe_b64decode(val.encode("utf-8"))


def _verify_jwt(token: str, secret: str) -> Optional[dict]:
    """
    Decodes and validates a standard HS256 JWT token using HMAC-SHA256.
    Returns decoded payload dict if valid and unexpired, None otherwise.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return None
    header_b64, payload_b64, sig_b64 = parts
    try:
        # Verify signature
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            f"{header_b64}.{payload_b64}".encode("utf-8"),
            "sha256",
        ).digest()
        actual_sig = _decode_base64_url(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Verify payload and expiration
        payload = json.loads(_decode_base64_url(payload_b64).decode("utf-8"))
        exp = payload.get("exp")
        if exp is not None and time.time() > float(exp):
            logger.warning("JWT token expired: exp=%s, current=%s", exp, time.time())
            return None
        return payload
    except Exception as e:
        logger.debug("JWT decode failed: %s", e)
        return None


async def verify_admin_key(x_admin_key: Optional[str] = Header(None)) -> str:
    """
    Dependency for admin-only endpoints.
    Uses constant-time comparison against ADMIN_API_KEY.
    Rejects empty, missing, or default development keys in production.
    """
    if not x_admin_key or not x_admin_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin key header missing or empty.",
        )

    configured_key = settings.admin_api_key or ""
    if not configured_key or not configured_key.strip():
        logger.error("ADMIN_API_KEY is not configured on the server")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin access not configured on server.",
        )

    if settings.is_production and configured_key == "dev-admin-key-change-in-production":
        logger.error("Insecure default ADMIN_API_KEY used in production environment")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Insecure admin key configuration.",
        )

    # Constant-time comparison to prevent timing side-channel attacks
    if not hmac.compare_digest(x_admin_key.strip(), configured_key.strip()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin key.",
        )
    return x_admin_key


async def get_optional_current_user(
    authorization: Optional[str] = Header(None),
) -> Optional[dict]:
    """
    Optional authentication: returns user dict if valid Bearer token provided,
    otherwise returns None without raising 401.
    """
    if not authorization:
        return None
    try:
        return await get_current_user(authorization=authorization)
    except HTTPException:
        return None


async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> dict:
    """
    Validates the authenticated caller via Bearer token.
    Checks:
    1. Supabase Auth service (if configured and online)
    2. Local JWT signed with settings.secret_key or Supabase JWT secret
    3. Authenticated session identity

    Returns user dictionary: {"id": str, "email": str, "role": str, "is_admin": bool}
    Raises 401 on missing, expired, or invalid credentials.
    """
    if not authorization or not authorization.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.strip().split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must follow format: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token cannot be empty.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Attempt 1: Validate via Supabase Auth
    try:
        from db.client import get_supabase
        sb = get_supabase()
        # Supabase Python client auth.get_user(jwt)
        user_res = sb.auth.get_user(token)
        if user_res and getattr(user_res, "user", None):
            u = user_res.user
            user_id = str(u.id)
            email = getattr(u, "email", None) or ""
            role = getattr(u, "role", "authenticated")
            return {
                "id": user_id,
                "email": email,
                "role": role,
                "is_admin": role == "admin" or email.endswith("@bbmp.gov.in"),
            }
    except Exception as sb_err:
        logger.debug("Supabase auth verification failed or bypassed: %s", sb_err)

    # Attempt 2: Validate against local JWT secret
    secrets_to_try = [settings.secret_key]
    if hasattr(settings, "supabase_service_role_key") and settings.supabase_service_role_key:
        secrets_to_try.append(settings.supabase_service_role_key)

    for sec in secrets_to_try:
        payload = _verify_jwt(token, sec)
        if payload:
            user_id = str(payload.get("sub") or payload.get("id") or payload.get("user_id") or "")
            if user_id:
                email = payload.get("email", "")
                role = payload.get("role", "authenticated")
                return {
                    "id": user_id,
                    "email": email,
                    "role": role,
                    "is_admin": role == "admin" or payload.get("is_admin", False),
                }

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid, expired, or unverified authentication token.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def create_access_token(user_id: str, email: str = "", expires_delta_seconds: int = 86400 * 30) -> str:
    """
    Creates a cryptographically signed HS256 JWT access token for user sessions.
    Valid for 30 days by default.
    """
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "id": str(user_id),
        "email": email or "",
        "iat": now,
        "exp": now + expires_delta_seconds,
        "role": "authenticated",
    }
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = hmac.new(
        settings.secret_key.encode("utf-8"),
        f"{header_b64}.{payload_b64}".encode("utf-8"),
        "sha256",
    ).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    return f"{header_b64}.{payload_b64}.{sig_b64}"


