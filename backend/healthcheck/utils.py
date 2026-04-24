import os
import numpy as np
from PIL import Image
from typing import Dict, List, Any

# --- CONFIG ---
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
# Path to the main project's data (used for context if needed, though not strictly by current inference)
DENGUE_DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "dengue_karnataka.csv"))

RISK_WEIGHTS = {
    "safe": 0.1,
    "benign": 0.3,
    "dangerous": 1.0
}

SAFE_CLASSES = ["normal", "clear_skin"]

BENIGN_CLASSES = [
    "melanocytic_nevus",
    "melanocytic_nevi",
    "nevus",
    "benign_lesion"
]

DANGEROUS_CLASSES = [
    "melanoma",
    "carcinoma",
    "basal_cell_carcinoma"
]

def get_label_type(label: str) -> str:
    if label in SAFE_CLASSES:
        return "safe"
    elif label in BENIGN_CLASSES:
        return "benign"
    elif label in DANGEROUS_CLASSES:
        return "dangerous"
    return "safe"

def determine_severity(label: str, confidence: float) -> tuple[str, float]:
    label_type = get_label_type(label)
    risk_score = confidence * RISK_WEIGHTS[label_type]

    if risk_score >= 0.75:
        return "high", risk_score
    elif risk_score >= 0.4:
        return "moderate", risk_score
    else:
        return "low", risk_score

def detect_visual_abnormality(image_path: str) -> bool:
    """Detects irregular patterns or high redness in skin images."""
    try:
        img = Image.open(image_path).convert("RGB")
        arr = np.array(img)

        variance = np.std(arr)
        red_channel = arr[:, :, 0]
        red_mean = np.mean(red_channel)

        if variance > 50 or red_mean > 140:
            return True
    except:
        pass
    return False

def build_safe_response(label: str, confidence: float, all_probs: Dict[str, float] = None, image_path: str = None) -> Dict[str, Any]:
    if all_probs:
        sorted_probs = sorted(all_probs.values(), reverse=True)
        if len(sorted_probs) > 1:
            gap = sorted_probs[0] - sorted_probs[1]
            if gap < 0.2:
                return {
                    "status": "uncertain",
                    "confidence": round(confidence, 2),
                    "severity": "low",
                    "message": "Model is not confident about the result.",
                    "why": ["Multiple possible conditions detected"],
                    "precautions": ["Upload clearer image"],
                    "disclaimer": "This is not a medical diagnosis."
                }

    severity, risk_score = determine_severity(label, confidence)
    
    # Visual Anomaly Override for skin
    abnormal = False
    if image_path and image_path.lower().endswith(('.jpg', '.jpeg', '.png')):
        abnormal = detect_visual_abnormality(image_path)

    if abnormal and severity == "low":
        severity = "moderate"

    # Status Text
    if severity == "low":
        status = "low concern"
    elif severity == "moderate":
        status = "moderate concern"
    else:
        status = "high concern"

    # Message
    if severity == "low":
        message = "No significant issue detected."
    elif severity == "moderate":
        if abnormal:
            message = "Visible irregular skin patterns detected. Monitor condition."
        else:
            message = "Some signs detected. Monitor condition."
    else:
        message = "Potential risk detected. Medical attention advised."

    why = []
    precautions = []

    if label in SAFE_CLASSES:
        why = ["No abnormal patterns detected"]
        precautions = ["Maintain normal hygiene", "Monitor for changes"]
    elif label in BENIGN_CLASSES:
        why = ["Pattern matches benign skin conditions"]
        precautions = ["Monitor for changes in size or color", "Consult a doctor if concerned"]
    elif label in DANGEROUS_CLASSES:
        why = ["Pattern matches known risk conditions"]
        precautions = ["Seek medical evaluation", "Avoid self-treatment"]

    return {
        "status": status,
        "confidence": round(confidence, 2),
        "risk_score": round(risk_score * 100, 1),
        "severity": severity,
        "message": message,
        "why": why,
        "precautions": precautions,
        "disclaimer": "This is not a medical diagnosis."
    }
