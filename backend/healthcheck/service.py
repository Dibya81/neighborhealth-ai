import os
import torch
import librosa
import json
from PIL import Image
from typing import Dict, Any
from transformers import (
    AutoModelForImageClassification, 
    AutoImageProcessor,
    AutoFeatureExtractor
)
from safetensors.torch import load_file

# Import local models from the moved package
from .cough_model_logic.models import ASTAudioClassifier

# --- CONFIG ---
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
SKIN_MODEL_PATH = os.path.join(MODELS_DIR, "skin_model")
COUGH_MODEL_PATH = os.path.join(MODELS_DIR, "cough_model")

class SkinInference:
    def __init__(self):
        try:
            self.processor = AutoImageProcessor.from_pretrained(SKIN_MODEL_PATH)
            self.model = AutoModelForImageClassification.from_pretrained(SKIN_MODEL_PATH)
            self.classes = self.model.config.id2label
        except Exception as e:
            print(f"Error loading skin model: {e}")
            self.model = None

    def predict(self, image_path: str) -> Dict[str, Any]:
        if not self.model:
            return {"error": "Model not loaded"}
        
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        logits = outputs.logits
        probs = torch.nn.functional.softmax(logits, dim=-1)
        confidence, pred_idx = torch.max(probs, dim=-1)
        
        label = self.classes[pred_idx.item()]
        # Standardize labels
        label = label.lower().replace(" ", "_")
        
        return {
            "label": label,
            "confidence": float(confidence),
            "all_probs": {self.classes[i]: float(probs[0][i]) for i in range(len(self.classes))}
        }

class CoughInference:
    def __init__(self):
        try:
            self.feature_extractor = AutoFeatureExtractor.from_pretrained(COUGH_MODEL_PATH)
            self.model = ASTAudioClassifier() 
            
            # Load weights from safetensors with key mapping
            weights_path = os.path.join(COUGH_MODEL_PATH, "model.safetensors")
            if os.path.exists(weights_path):
                raw_weights = load_file(weights_path)
                # Map 'audio_spectrogram_transformer' -> 'ast' for the wrapper class
                mapped_weights = {}
                for k, v in raw_weights.items():
                    new_key = k.replace("audio_spectrogram_transformer", "ast")
                    mapped_weights[new_key] = v
                
                self.model.load_state_dict(mapped_weights, strict=False)
                self.model.eval()
            
            with open(os.path.join(COUGH_MODEL_PATH, "config.json")) as f:
                config = json.load(f)
                self.classes = config.get("id2label", {})
                
        except Exception as e:
            print(f"Error loading custom cough model: {e}")
            self.model = None

    def predict(self, audio_path: str) -> Dict[str, Any]:
        if not self.model or not os.path.exists(audio_path):
            return {"error": "Model not loaded or file missing", "label": "uncertain", "confidence": 0.0}
        
        try:
            # sr=16000 is critical for AST models
            y, sr = librosa.load(audio_path, sr=16000)
            
            if len(y) == 0:
                raise ValueError("Loaded audio is empty")
                
            # Truncate or pad to expected length if necessary (AST usually handles variable T but check)
            inputs = self.feature_extractor(y, sampling_rate=16000, return_tensors="pt")
            
            with torch.no_grad():
                logits = self.model(inputs["input_values"])
                prob = torch.sigmoid(logits)
                conf = float(prob.item())
                
                # Binary mapping based on typical COVID/Healthy binary datasets used in these repos
                label = "cough" if conf > 0.5 else "normal"
                
            return {
                "label": label,
                "confidence": conf,
                "all_probs": {"normal": 1.0 - conf, "cough": conf}
            }
        except Exception as e:
            print(f"Cough prediction failed: {e}")
            return {
                "error": str(e),
                "label": "uncertain",
                "confidence": 0.0
            }
