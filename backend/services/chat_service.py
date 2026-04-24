import time
import httpx
import json
from typing import Optional
from fastapi import HTTPException, status
from db.wards import get_ward_by_id
from db.risk_scores import get_latest_score_for_ward
from config import get_settings
from utils.logger import get_logger

logger = get_logger("AI")

SYSTEM_PROMPT = """You are a health intelligence assistant for NeighborHealth.

You ONLY answer questions related to:
- Disease risk (dengue, malaria, heatstroke)
- Weather impact on health
- Area safety and health conditions
- Prevention and symptoms

If a question is outside this scope, reply:
"I can only assist with health and disease-related queries in this system."
"""


def is_health_query(msg: str) -> bool:
    keywords = [
        "risk", "safe", "area", "health", "dengue", "malaria", "fever",
        "weather", "sick", "doctor", "hospital", "ill", "symptom", "prevention",
        "what", "should", "outside", "travel", "today", "summary", "forecast",
        "past", "condition", "disease", "outbreak", "alert", "score",
    ]
    return any(k in msg.lower() for k in keywords)


def _get_sim_context(ward_id: str, mode: str) -> str:
    try:
        id_val = int(ward_id)
    except Exception:
        id_val = 0

    factors = []
    if mode == "monsoon":
        if id_val % 7 == 0 or id_val % 11 == 0:
            factors.append("proximity to water bodies")
        if id_val % 5 == 0 or id_val % 13 == 0:
            factors.append("poor drainage infrastructure")
        if id_val % 4 == 0:
            factors.append("low-lying area prone to pooling")
        desc = "2025 Monsoon Outbreak Simulation (Heavy Rainfall conditions)"
    elif mode == "pollution":
        if id_val % 17 == 0:
            factors.append("industrial output")
        if id_val % 9 == 0:
            factors.append("post-Diwali open burning")
        if id_val % 3 == 0:
            factors.append("high population density and vehicle traffic")
        desc = "2025 Post-Diwali Pollution Crisis Simulation (Nov conditions)"
    elif mode == "cold":
        if id_val % 3 == 0:
            factors.append("high density housing")
        if id_val % 6 == 0:
            factors.append("crowded market proximity")
        desc = "2025 Winter Health Crisis Simulation (Cold Wave conditions)"
    else:
        return ""

    factor_str = ", ".join(factors) if factors else "general seasonal factors"
    return (
        f"\n[SIMULATION ACTIVE]\nScenario: {desc}\n"
        f"Critical Factors in this ward: {factor_str}\n"
        f"Note: The risk scores shown on the map are CURRENTLY SIMULATED for this scenario."
    )


def generate_ward_advisory(
    ward_id: str,
    user_message: str,
    language: str = "en",
    simulation_mode: Optional[str] = None,
    user_health_conditions: Optional[list] = None,
) -> dict:
    logger.info("Incoming request - Ward: %s, Message: %s, Sim: %s", ward_id, user_message, simulation_mode)

    if not is_health_query(user_message):
        logger.warning("Rejected non-health query: %s", user_message)
        return {
            "response": "I can only assist with health and disease-related queries in this system.",
            "ward_id": ward_id,
            "ward_context_used": False,
            "language": language,
        }

    is_city = ward_id.lower() == "city"
    ward = None
    score = None
    context_used = False

    if is_city:
        ward = {"name": "Bengaluru (City-wide)"}
        risk_score = 50.0
        risk_level = "mixed"
        signals = {"disease_label": "All Monitored Diseases"}
    else:
        ward = get_ward_by_id(ward_id)
        if not ward:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ward {ward_id} not found.",
            )
        score = get_latest_score_for_ward(ward_id)
        context_used = score is not None
        risk_score = score["risk_score"] if score else 50.0
        risk_level = score["risk_level"] if score else "unknown"
        signals = {
            "rainfall_7d": score.get("rainfall_7d", 0) if score else 0,
            "cases": score.get("dengue_cases", 0) or score.get("case_count", 0) if score else 0,
            "alerts": score.get("report_count", 0) or score.get("alert_count", 0) if score else 0,
            "disease_label": score.get("disease_id", "General").replace("_", " ").title() if score else "General Health",
        }

    sim_context = _get_sim_context(ward_id, simulation_mode) if (simulation_mode and not is_city) else ""

    health_ctx = ""
    if user_health_conditions:
        conds = ", ".join(user_health_conditions)
        health_ctx = (
            f"\n[USER HEALTH PROFILE]\nKnown conditions: {conds}\n"
            f"IMPORTANT: Tailor advice for these conditions."
        )

    if is_city:
        prompt_payload = (
            f"Context: All of Bengaluru city.\n"
            f"Instructions: Provide a high-level city-wide health intelligence summary. "
            f"Focus on the general seasonal patterns in Bengaluru. "
            f"If it's monsoon (June-Oct), mention Dengue/Malaria. If summer, mention Heatstroke. "
            f"Return in {language}.\n\n"
            f"{health_ctx}\nUser Query: {user_message}"
        )
    else:
        prompt_payload = (
            f"Context:\nWard: {ward['name']} (Ward {ward_id})\n"
            f"Active Disease Focus: {signals.get('disease_label', 'General Health')}\n"
            f"Live Risk Score: {int(risk_score)}/100 ({risk_level.upper()})\n"
            f"Key Signals (Live DB):\n"
            f"- Rainfall (last 7d): {float(signals.get('rainfall_7d', 0)):.1f}mm\n"
            f"- Reported Cases: {int(signals.get('cases', 0))}\n"
            f"- Community Alerts: {int(signals.get('alerts', 0))}\n"
            f"{sim_context}\n"
            f"{health_ctx}\n\n"
            f"Instructions: Use the context above to answer. If a simulation is active, EXPLAIN that you are analyzing the 2025 hypothetical scenario. Return in {language}.\n\n"
            f"User Query: {user_message}"
        )

    settings = get_settings()

    try:
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not configured in .env — AI responses unavailable.")

        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "NeighborHealth",
        }

        body = {
            "model": "google/gemini-2.0-flash-001",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_payload},
            ],
        }

        start_time = time.time()
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=body,
            )

        duration = time.time() - start_time
        response.raise_for_status()
        data = response.json()

        logger.info("Response generated (%.1fs)", duration)
        response_text = data["choices"][0]["message"]["content"]

    except ValueError as ve:
        logger.error("Config error: %s", ve)
        response_text = str(ve)
    except Exception as err:
        logger.error("OpenRouter error: %s", err)
        response_text = "AI service is temporarily unavailable. Please try again later."

    return {
        "response": response_text,
        "ward_id": ward_id,
        "ward_context_used": context_used,
        "language": language,
    }
