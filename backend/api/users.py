from fastapi import APIRouter, HTTPException, status
from models.user import UserCreate, UserResponse
from db.users import upsert_user, get_ai_history
from db.client import get_supabase
from utils.logger import get_logger

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
    """
    try:
        user = upsert_user(
            name=payload.name,
            email=payload.email,
            phone=payload.phone,
            lat=payload.lat,
            lng=payload.lng,
            home_ward_id=payload.home_ward_id,
            health_conditions=payload.health_conditions,
            saved_locations=[loc.dict() for loc in payload.saved_locations] if payload.saved_locations else []
        )
        logger.info("User created/updated: %s", user.get("id"))
        return user
    except Exception as e:
        logger.error("Error upserting user: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not upsert user: {str(e)}"
        )

@router.get("/users/{user_id}/history", tags=["users"])
async def get_history(user_id: str):
    """Retrieves AI suggestion history for the user."""
    try:
        return {"history": get_ai_history(user_id)}
    except Exception as e:
        logger.error("Error fetching history: %s", e)
        return {"history": []}

@router.put("/users/{user_id}", response_model=UserResponse, tags=["users"])
async def update_user(user_id: str, payload: UserCreate):
    """Updates an existing user profile."""
    try:
        sb = get_supabase()
        # Filter out None values to prevent overwriting with nulls
        data = {k: v for k, v in payload.dict().items() if v is not None}
        
        # Handle complex types for JSONB
        if 'saved_locations' in data and data['saved_locations']:
            data['saved_locations'] = [loc if isinstance(loc, dict) else loc for loc in data['saved_locations']]

        result = sb.table("users").update(data).eq("id", user_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error updating user: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
