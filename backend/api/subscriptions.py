from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Header
from models.subscription import SubscriptionCreate, SubscriptionResponse, CancelResponse
from db.wards import ward_exists
from db.subscriptions import upsert_subscription, cancel_subscription, get_subscription_by_id
from utils.logger import get_logger
from api.deps import get_optional_current_user, get_current_user

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["subscriptions"],
)
async def create_subscription(
    payload: SubscriptionCreate,
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    """
    Subscribe for risk alerts for a specific ward.
    Idempotent — calling twice with same ward_id + contact re-activates the subscription.
    Associates with authenticated citizen identity when signed in.
    """
    if not ward_exists(payload.ward_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ward {payload.ward_id} not found.",
        )

    # If caller is logged in, attach their verified user_id
    effective_user_id = current_user["id"] if current_user else payload.user_id

    sub = upsert_subscription(
        ward_id=payload.ward_id,
        contact=payload.contact,
        contact_type=payload.contact_type,
        threshold=payload.threshold or 70,
        user_id=effective_user_id,
        name=payload.name,
        email=payload.email,
        notify_diseases=payload.notify_diseases,
    )

    logger.info("Subscription upserted: ward=%s type=%s user=%s", payload.ward_id, payload.contact_type, effective_user_id)
    return SubscriptionResponse(
        id=sub["id"],
        ward_id=sub["ward_id"],
        contact=sub["contact"],
        contact_type=sub["contact_type"],
        threshold=sub["threshold"],
        user_id=sub.get("user_id"),
        name=sub.get("name"),
        email=sub.get("email"),
        notify_diseases=sub.get("notify_diseases", ["dengue"]),
        active=sub.get("active", True),
    )


@router.delete("/subscriptions/{subscription_id}", response_model=CancelResponse, tags=["subscriptions"])
async def cancel(
    subscription_id: str,
    authorization: Optional[str] = Header(None),
):
    """
    Unsubscribes from alerts. Soft-delete — sets active=False.
    Validates ownership: User-owned subscriptions require valid authorization.
    """
    sub = get_subscription_by_id(subscription_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found.",
        )

    # If subscription is tied to a user account, enforce ownership
    if sub.get("user_id"):
        user = await get_current_user(authorization=authorization)
        if str(sub["user_id"]) != str(user["id"]) and not user.get("is_admin"):
            logger.warning(
                "Unauthorized subscription cancel attempt: actor=%s owner=%s sub=%s",
                user["id"],
                sub["user_id"],
                subscription_id,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You can only cancel subscriptions belonging to your account.",
            )

    result = cancel_subscription(subscription_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found.",
        )
    return CancelResponse(id=subscription_id, status="cancelled")

