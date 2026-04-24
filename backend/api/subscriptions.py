from fastapi import APIRouter, HTTPException, status
from models.subscription import SubscriptionCreate, SubscriptionResponse, CancelResponse
from db.wards import ward_exists
from db.subscriptions import upsert_subscription, cancel_subscription
from utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/subscriptions",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["subscriptions"],
)
async def create_subscription(payload: SubscriptionCreate):
    """
    Subscribe for risk alerts for a specific ward.
    Idempotent — calling twice with same ward_id + contact re-activates the subscription.
    """
    if not ward_exists(payload.ward_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ward {payload.ward_id} not found.",
        )

    sub = upsert_subscription(
        ward_id=payload.ward_id,
        contact=payload.contact,
        contact_type=payload.contact_type,
        threshold=payload.threshold or 70,
        user_id=payload.user_id,
        name=payload.name,
        email=payload.email,
        notify_diseases=payload.notify_diseases,
    )

    logger.info("Subscription upserted: ward=%s type=%s", payload.ward_id, payload.contact_type)
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
async def cancel(subscription_id: str):
    """Unsubscribes from alerts. Soft-delete — sets active=False."""
    result = cancel_subscription(subscription_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription not found.",
        )
    return CancelResponse(id=subscription_id, status="cancelled")
