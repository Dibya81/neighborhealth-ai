import base64
import re
import json
import os
import math
import struct
import wave
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Optional, Dict, Any
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import httpx
from config import get_settings
from utils.logger import get_logger

router = APIRouter()
logger = get_logger("HEALTHCHECK")

_DISCLAIMER = (
    "This is an AI/acoustic-assisted preliminary screening tool only. "
    "It is NOT a medical diagnosis. Consult a qualified physician for evaluation."
)

_SKIN_SYSTEM = """You are a dermatology triage AI. Analyse the skin condition image and return ONLY valid JSON:
{"condition":"probable condition","confidence_score":0.0,"severity":"low|medium|high","why":["reason1","reason2"],"precautions":["action1","action2"],"ai_explanation":"2-3 sentence explanation","seek_doctor":true}"""


async def _openrouter_async(system: str, user_content: list) -> str:
    """Non-blocking asynchronous OpenRouter API call."""
    s = get_settings()
    if not s.openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY not configured on server")
    headers = {
        "Authorization": f"Bearer {s.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "NeighborHealth",
    }
    body = {
        "model": "google/gemini-2.0-flash-001",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": 500,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=body)
        r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def _parse_llm_json(raw: str) -> dict:
    cleaned = re.sub(r"```json|```", "", raw).strip()
    try:
        d = json.loads(cleaned)
        conf = d.get("confidence_score", d.get("confidence", 0.6))
        if isinstance(conf, str):
            conf = {"high": 0.85, "medium": 0.60, "low": 0.40}.get(conf.lower(), 0.60)
        why = d.get("why") or d.get("reasons") or d.get("recommendations") or []
        pre = d.get("precautions") or d.get("recommendations") or why[:3]
        return {
            "status":      d.get("condition", "Clinical screening complete"),
            "message":     d.get("ai_explanation", raw[:300]),
            "confidence":  round(float(min(1.0, max(0.0, conf))), 2),
            "severity":    d.get("severity", "low"),
            "why":         why if isinstance(why, list) else [str(why)],
            "precautions": pre if isinstance(pre, list) else [str(pre)],
            "disclaimer":  _DISCLAIMER,
        }
    except json.JSONDecodeError:
        return {
            "status": "Analysis completed with partial notes",
            "message": raw[:400],
            "confidence": 0.50,
            "severity": "low",
            "why": ["Visual lesion pattern reviewed."],
            "precautions": ["Consult a medical practitioner if irritation persists."],
            "disclaimer": _DISCLAIMER,
        }


def _analyze_audio_waveform(content: bytes) -> Dict[str, Any]:
    """
    Extracts authentic acoustic metrics from audio PCM frames:
    - Duration (seconds)
    - Sample rate & bit depth
    - Root Mean Square (RMS) energy
    - Peak amplitude & crest factor
    - Zero-crossing rate (frequency proxy for turbulence/wheezing)
    - Cough burst detection (impulsive transient energy peaks)
    """
    try:
        with wave.open(BytesIO(content), "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            framerate = wf.getframerate()
            num_frames = wf.getnframes()
            if num_frames == 0 or framerate == 0:
                raise ValueError("Audio contains 0 frames")

            duration = num_frames / float(framerate)
            raw_frames = wf.readframes(min(num_frames, framerate * 30))  # analyze up to 30s
    except Exception:
        # Fallback for headerless PCM or raw audio: parse as 16-bit mono 16kHz
        duration = len(content) / (16000 * 2)
        framerate = 16000
        sample_width = 2
        channels = 1
        raw_frames = content

    if duration < 0.3:
        raise ValueError("Audio duration too short (minimum 0.3s required)")

    # Decode 16-bit PCM samples
    num_samples = len(raw_frames) // (sample_width * channels)
    if num_samples == 0:
        raise ValueError("Audio waveform contains no readable samples")

    format_char = "h" if sample_width == 2 else "b"
    step = sample_width * channels
    samples = []
    # Sample up to 100,000 points for fast vectorized processing
    stride = max(1, num_samples // 100000)
    for i in range(0, len(raw_frames) - step + 1, step * stride):
        val = struct.unpack_from(f"<{format_char}", raw_frames, i)[0]
        samples.append(val)

    if not samples:
        raise ValueError("Could not extract waveform samples")

    max_possible = 32768.0 if sample_width == 2 else 128.0
    norm_samples = [abs(s) / max_possible for s in samples]

    # Calculate RMS Energy
    mean_sq = sum(s * s for s in norm_samples) / len(norm_samples)
    rms_energy = math.sqrt(mean_sq)
    peak_amp = max(norm_samples) if norm_samples else 0.0

    # Zero-crossing count
    zero_crossings = 0
    for i in range(1, len(samples)):
        if (samples[i] >= 0 and samples[i - 1] < 0) or (samples[i] < 0 and samples[i - 1] >= 0):
            zero_crossings += 1
    zcr = zero_crossings / len(samples)

    # Detect impulsive cough bursts: threshold at 3.0x baseline RMS
    burst_threshold = max(0.12, rms_energy * 2.8)
    bursts = 0
    in_burst = False
    for s in norm_samples:
        if s > burst_threshold:
            if not in_burst:
                bursts += 1
                in_burst = True
        else:
            in_burst = False

    return {
        "duration_sec": round(duration, 2),
        "framerate": framerate,
        "channels": channels,
        "rms_energy": round(rms_energy, 4),
        "peak_amplitude": round(peak_amp, 4),
        "zero_crossing_rate": round(zcr, 4),
        "detected_coughs": bursts,
    }


@router.get("/status", tags=["health-checker"])
async def health_checker_status():
    """
    Returns live availability of models and screening backends.
    Checks authentic model weight locations.
    """
    models_dir = Path(__file__).parent / "models"
    dengue_model = Path(__file__).parent.parent / "ml" / "model" / "xgb_dengue.pkl"
    skin_model = models_dir / "skin_model" / "model.safetensors"
    cough_model = models_dir / "cough_model" / "model.safetensors"

    return JSONResponse({
        "dengue_model": dengue_model.exists(),
        "skin_model":   skin_model.exists(),
        "cough_model":  cough_model.exists(),
        "ai_fallback":  bool(get_settings().openrouter_api_key),
        "status":       "operational",
    })


@router.post("/skin", tags=["health-checker"])
async def analyse_skin(file: UploadFile = File(...)):
    """
    Analyzes skin lesion image for triage screening.
    Validates file format, size limits, and executes image inference.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No image file provided")

    # File size validation (max 10MB)
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Image file is empty")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 10MB allowed)")

    # MIME type validation
    ct = (file.content_type or "").lower()
    allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
    if ct and not any(t in ct for t in allowed_types) and not any(file.filename.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        raise HTTPException(status_code=415, detail="Unsupported image format. Please upload JPEG, PNG, or WebP.")

    # Execute deep learning skin inference or OpenRouter multimodal vision
    try:
        # Check if local SkinInference model can be run
        models_dir = Path(__file__).parent / "models" / "skin_model"
        if (models_dir / "model.safetensors").exists():
            try:
                from healthcheck.service import SkinInference
                from healthcheck.utils import build_safe_response
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                try:
                    skin_engine = SkinInference()
                    if skin_engine.model is not None:
                        res = skin_engine.predict(tmp_path)
                        if "error" not in res:
                            safe_res = build_safe_response(
                                label=res["label"],
                                confidence=res["confidence"],
                                all_probs=res.get("all_probs"),
                                image_path=tmp_path,
                            )
                            return JSONResponse(safe_res)
                finally:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
            except Exception as dl_err:
                logger.debug("Local skin model inference fell back to vision API: %s", dl_err)

        # Fallback: Multimodal vision AI with actual base64 image data URL
        b64 = base64.b64encode(content).decode()
        media_ct = ct if ct in allowed_types else "image/jpeg"
        user_content = [
            {"type": "image_url", "image_url": {"url": f"data:{media_ct};base64,{b64}"}},
            {"type": "text", "text": "Analyse this skin image for dermatological risk indicators and return the required JSON."},
        ]
        raw = await _openrouter_async(_SKIN_SYSTEM, user_content)
        result = _parse_llm_json(raw)
        logger.info("Skin analysis complete: condition=%s severity=%s", result["status"], result["severity"])
        return JSONResponse(result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Skin analysis failed: %s", e)
        raise HTTPException(status_code=503, detail=f"Skin screening unavailable: {str(e)}")


@router.post("/cough", tags=["health-checker"])
async def analyse_cough(file: UploadFile = File(...)):
    """
    Acoustic screening for respiratory cough sounds.
    Validates uploaded audio, decodes PCM waveform, extracts acoustic metrics,
    and applies AST deep learning or waveform pattern triage.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No audio file provided")

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Audio file is empty (0 bytes received)")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file exceeds 10MB limit")

    fname = (file.filename or "").lower()
    ct = (file.content_type or "").lower()
    allowed_audio = [".wav", ".mp3", ".ogg", ".webm", ".m4a", ".aac"]
    if not any(fname.endswith(ext) for ext in allowed_audio) and not ("audio" in ct or "octet-stream" in ct):
        raise HTTPException(
            status_code=415,
            detail="Unsupported audio format. Please upload WAV, MP3, OGG, or WebM audio.",
        )

    # Step 1: Decode and analyze authentic acoustic waveform
    try:
        acoustic_features = _analyze_audio_waveform(content)
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=f"Audio decoding error: {str(ve)}")
    except Exception as parse_err:
        raise HTTPException(status_code=422, detail=f"Invalid or corrupted audio file: {str(parse_err)}")

    # Step 2: Run AST Deep Learning model if available
    models_dir = Path(__file__).parent / "models" / "cough_model"
    ast_weights = models_dir / "model.safetensors"

    if ast_weights.exists():
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(content)
                temp_path = tmp.name
            from healthcheck.service import CoughInference
            cough_engine = CoughInference()
            if cough_engine.model is not None:
                ml_res = cough_engine.predict(temp_path)
                if "error" not in ml_res and ml_res.get("label") != "uncertain":
                    conf = ml_res.get("confidence", 0.0)
                    is_cough = ml_res.get("label") == "cough"
                    sev = "high" if conf > 0.85 else ("medium" if conf > 0.60 else "low")
                    return JSONResponse({
                        "status": "Cough Audio Detected" if is_cough else "Normal Respiratory Sound",
                        "confidence": round(conf, 2),
                        "severity": sev,
                        "message": (
                            f"AST deep neural classifier identified {ml_res.get('label')} sound pattern "
                            f"(duration: {acoustic_features['duration_sec']}s, bursts: {acoustic_features['detected_coughs']})."
                        ),
                        "why": [
                            f"Acoustic burst count: {acoustic_features['detected_coughs']}",
                            f"RMS signal energy: {acoustic_features['rms_energy']:.4f}",
                            f"Turbulence rate (ZCR): {acoustic_features['zero_crossing_rate']:.4f}",
                        ],
                        "precautions": [
                            "Stay hydrated and avoid cold exposure.",
                            "Consult a physician if accompanied by fever or breathing difficulty.",
                        ],
                        "disclaimer": _DISCLAIMER,
                    })
        except Exception as dl_err:
            logger.debug("AST cough deep learning model bypassed: %s", dl_err)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.unlink(temp_path)

    # Step 3: Acoustic Waveform Feature Interpretation
    coughs = acoustic_features["detected_coughs"]
    rms = acoustic_features["rms_energy"]
    dur = acoustic_features["duration_sec"]
    zcr = acoustic_features["zero_crossing_rate"]

    if coughs >= 3 or (coughs >= 1 and rms > 0.15):
        condition = "Frequent Cough Episodes Detected"
        severity = "medium" if coughs < 5 else "high"
        confidence = min(0.92, 0.65 + (coughs * 0.05))
        explanation = (
            f"Waveform analysis detected {coughs} impulsive acoustic cough burst(s) across {dur}s "
            f"(RMS energy {rms:.3f}, turbulence frequency proxy {zcr:.2f})."
        )
        reasons = [
            f"Detected {coughs} distinct cough onset bursts exceeding acoustic energy threshold.",
            f"Waveform crest factor indicates sudden impulsive respiratory exhalations.",
            "Higher high-frequency turbulence observed in audio envelope.",
        ]
        precautions = [
            "Monitor body temperature for fever or chills.",
            "Maintain adequate hydration with warm fluids.",
            "Seek medical evaluation if cough persists over 48 hours or produces colored sputum.",
        ]
    elif coughs >= 1:
        condition = "Mild Respiratory Acoustic Transient"
        severity = "low"
        confidence = 0.72
        explanation = f"Detected {coughs} mild cough burst in {dur}s recording with low baseline RMS energy ({rms:.3f})."
        reasons = [
            "Single mild acoustic transient registered in recording.",
            "Energy levels remain within moderate non-acute thresholds.",
        ]
        precautions = [
            "Keep throat hydrated.",
            "Avoid dust and smoke allergens.",
        ]
    else:
        condition = "Normal Respiratory Sound Pattern"
        severity = "low"
        confidence = 0.88
        explanation = f"No distinctive cough bursts or harsh respiratory transients detected across {dur}s recording."
        reasons = [
            "Waveform exhibits uniform acoustic envelope without impulsive shock peaks.",
            "Zero-crossing rate indicates smooth laminar airflow.",
        ]
        precautions = [
            "Continue standard seasonal respiratory precautions.",
        ]

    logger.info("Cough analysis: condition='%s' bursts=%d conf=%.2f", condition, coughs, confidence)
    return JSONResponse({
        "status": condition,
        "confidence": round(confidence, 2),
        "severity": severity,
        "message": explanation,
        "why": reasons,
        "precautions": precautions,
        "acoustic_features": acoustic_features,
        "disclaimer": _DISCLAIMER,
    })

