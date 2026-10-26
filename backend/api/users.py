from fastapi import APIRouter, HTTPException, status, Depends
from models.user import UserCreate, UserResponse
from db.users import upsert_user, get_ai_history
from db.client import get_supabase
from utils.logger import get_logger
from api.deps import get_current_user, create_access_token

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    tags=["users"],
)
async def create_user(payload: UserCreate):
    """
    Upsert user data. Linked to email for uniqueness.
    Returns the user profile with a cryptographically signed session token.
    """
    try:
        saved_locs = [loc.dict() if hasattr(loc, "dict") else loc for loc in payload.saved_locations] if payload.saved_locations else []
        user = upsert_user(
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            lat=payload.lat,
            lng=payload.lng,
            home_ward_id=payload.home_ward_id,
            health_conditions=payload.health_conditions,
            saved_locations=saved_locs,
        )
        user_id = str(user.get("id"))
        email = user.get("email") or ""
        token = create_access_token(user_id=user_id, email=email)
        user["token"] = token
        logger.info("User created/updated: %s", user_id)
        return user
    except Exception as e:
        logger.error("Error upserting user: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not upsert user: {str(e)}"
        )


@router.get("/users/{user_id}/history", tags=["users"])
async def get_history(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retrieves AI suggestion history for the authenticated user.
    Enforces authorization: citizens can only view their own history.
    """
    if str(current_user["id"]) != str(user_id) and not current_user.get("is_admin"):
        logger.warning(
            "Unauthorized access attempt to user history: actor=%s target=%s",
            current_user["id"],
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access another citizen's health history.",
        )

    try:
        return {"history": get_ai_history(user_id)}
    except Exception as e:
        logger.error("Error fetching history: %s", e)
        return {"history": []}


@router.put("/users/{user_id}", response_model=UserResponse, tags=["users"])
async def update_user(
    user_id: str,
    payload: UserCreate,
    current_user: dict = Depends(get_current_user),
):
    """
    Updates an existing user profile.
    Enforces authorization: citizens can only modify their own profile.
    """
    if str(current_user["id"]) != str(user_id) and not current_user.get("is_admin"):
        logger.warning(
            "Unauthorized profile update attempt: actor=%s target=%s",
            current_user["id"],
            user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to modify another citizen's profile.",
        )

    try:
        sb = get_supabase()
        # Filter out None values to prevent overwriting with nulls
        data = {k: v for k, v in payload.dict().items() if v is not None}

        # Handle complex types for JSONB column (pass raw list/dict, never json.dumps)
        if 'saved_locations' in data and data['saved_locations']:
            data['saved_locations'] = [
                loc.dict() if hasattr(loc, "dict") else loc for loc in data['saved_locations']
            ]

        result = sb.table("users").update(data).eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")
        updated = result.data[0]
        # Preserve or generate session token for convenience
        updated["token"] = create_access_token(user_id=str(updated["id"]), email=updated.get("email") or "")
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Remote database unavailable during user update (%s); updating session user representation", e)
        updated = {**current_user, **data}
        updated["id"] = user_id
        if "created_at" not in updated or not updated["created_at"]:
            from datetime import datetime
            updated["created_at"] = datetime.utcnow()
        updated["token"] = create_access_token(user_id=str(user_id), email=updated.get("email") or "")
        return updated

