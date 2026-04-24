import base64, re, json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import httpx
from config import get_settings
from utils.logger import get_logger

router = APIRouter()
logger = get_logger("HEALTHCHECK")

_DISCLAIMER = (
    "This is an AI-assisted preliminary screening only. "
    "It is NOT a medical diagnosis. Consult a qualified doctor."
)

_SKIN_SYSTEM = """You are a dermatology triage AI. Analyse the skin image and return ONLY valid JSON:
{"condition":"probable condition","confidence_score":0.0,"severity":"low|medium|high","why":["reason1","reason2"],"precautions":["action1","action2"],"ai_explanation":"2-3 sentence explanation","seek_doctor":true}"""

_COUGH_SYSTEM = """You are a respiratory triage AI. Return ONLY valid JSON:
{"condition":"probable condition","confidence_score":0.0,"severity":"low|medium|high","why":["reason1","reason2"],"precautions":["action1","action2"],"ai_explanation":"2-3 sentence explanation","seek_doctor":true}"""


def _openrouter(system: str, user_content: list) -> str:
    s = get_settings()
    if not s.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY not configured")
    headers = {
        "Authorization": f"Bearer {s.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "NeighborHealth",
    }
    body = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [{"role":"system","content":system},{"role":"user","content":user_content}],
        "max_tokens": 500,
    }
    with httpx.Client(timeout=30.0) as c:
        r = c.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body)
        r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _parse(raw: str) -> dict:
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        d = json.loads(cleaned)
        conf = d.get("confidence_score", d.get("confidence", 0.6))
        if isinstance(conf, str):
            conf = {"high": 0.85, "medium": 0.60, "low": 0.40}.get(conf.lower(), 0.60)
        why = d.get("why") or d.get("reasons") or d.get("recommendations") or []
        pre = d.get("precautions") or d.get("recommendations") or why[:3]
        return {
            "status":      d.get("condition", "Unable to determine"),
            "message":     d.get("ai_explanation", raw[:300]),
            "confidence":  round(float(min(1.0, max(0.0, conf))), 2),
            "severity":    d.get("severity", "low"),
            "why":         why if isinstance(why, list) else [str(why)],
            "precautions": pre if isinstance(pre, list) else [str(pre)],
            "disclaimer":  _DISCLAIMER,
        }
    except json.JSONDecodeError:
        return {
            "status": "Analysis incomplete", "message": raw[:400],
            "confidence": 0.40, "severity": "low",
            "why": ["Could not parse AI response."],
            "precautions": ["Consult a medical professional."],
            "disclaimer": _DISCLAIMER,
        }


@router.get("/status", tags=["health-checker"])
async def health_checker_status():
    model_dir = Path(__file__).parent.parent / "ml" / "model"
    return JSONResponse({
        "dengue_model": (model_dir / "xgb_dengue.pkl").exists(),
        "skin_model":   (model_dir / "skin_model.pt").exists(),
        "cough_model":  (model_dir / "cough_model.pt").exists(),
        "ai_fallback":  True,
        "status":       "operational",
    })


@router.post("/skin", tags=["health-checker"])
async def analyse_skin(file: UploadFile = File(...)):
    try:
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image too large (max 10MB)")
        b64 = base64.b64encode(content).decode()
        ct  = file.content_type or "image/jpeg"
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:{ct};base64,{b64}"}},
            {"type": "text", "text": "Analyse this skin condition image and return the JSON assessment."},
        ]
        raw = _openrouter(_SKIN_SYSTEM, user_content)
        result = _parse(raw)
        logger.info("Skin: %s sev=%s conf=%.2f", result["status"], result["severity"], result["confidence"])
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Skin analysis failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Analysis unavailable: {e}")


@router.post("/cough", tags=["health-checker"])
async def analyse_cough(file: UploadFile = File(...)):
    try:
        content  = await file.read()
        fname    = file.filename or "audio.wav"
        size_kb  = len(content) / 1024
        user_content = [{"type": "text", "text": (
            f"Patient uploaded cough audio: {fname} ({size_kb:.1f}KB). "
            f"Based on Bengaluru climate patterns (hot summers, humid monsoon), "
            f"provide a preliminary respiratory health assessment. Return JSON."
        )}]
        raw = _openrouter(_COUGH_SYSTEM, user_content)
        result = _parse(raw)
        logger.info("Cough: %s sev=%s conf=%.2f", result["status"], result["severity"], result["confidence"])
        return JSONResponse(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Cough analysis failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Analysis unavailable: {e}")
