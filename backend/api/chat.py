from fastapi import APIRouter
from models.chat import ChatRequest, ChatResponse
from services.chat_service import generate_ward_advisory
from utils.logger import get_logger

router = APIRouter()
logger = get_logger(__name__)

@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(payload: ChatRequest):
    """
    AI-powered ward advisory endpoint with personalization and history tracking.
    """
    result = generate_ward_advisory(
        ward_id=payload.ward_id,
        user_message=payload.message,
        language=payload.language or "en",
        simulation_mode=payload.simulation_mode,
        user_health_conditions=payload.user_health_conditions,
    )

    # Save to history if user_id provided
    if payload.user_id:
        try:
            from db.users import save_ai_suggestion
            from db.risk_scores import get_latest_score_for_ward
            
            # Fetch context for history record
            score = get_latest_score_for_ward(payload.ward_id)
            save_ai_suggestion(
                user_id=payload.user_id,
                ward_id=payload.ward_id,
                disease_id=score.get("disease_id", "dengue") if score else "dengue",
                message=payload.message,
                response=result["response"],
                context={"risk_score": score.get("risk_score") if score else None},
            )
            logger.info("Saved AI suggestion to history for user %s", payload.user_id)
        except Exception as e:
            logger.error("Failed to save history: %s", e)
            pass  # Never block the response for history save failures

    return ChatResponse(**result)
