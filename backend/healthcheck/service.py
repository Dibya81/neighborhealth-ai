import os
import json
from typing import Dict, Any

# --- CONFIG ---
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
SKIN_MODEL_PATH = os.path.join(MODELS_DIR, "skin_model")
COUGH_MODEL_PATH = os.path.join(MODELS_DIR, "cough_model")

class SkinInference:
    def __init__(self):
        try:
            from PIL import Image
            import torch
            from transformers import AutoModelForImageClassification, AutoImageProcessor
            self.Image = Image
            self.torch = torch
            self.processor = AutoImageProcessor.from_pretrained(SKIN_MODEL_PATH)
            self.model = AutoModelForImageClassification.from_pretrained(SKIN_MODEL_PATH)
            self.classes = self.model.config.id2label
        except Exception as e:
            self.model = None
            self.classes = {}

    def predict(self, image_path: str) -> Dict[str, Any]:
        if not self.model:
            return {"error": "Model not loaded"}
        
        image = self.Image.open(image_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        
        with self.torch.no_grad():
            outputs = self.model(**inputs)
        
        logits = outputs.logits
        probs = self.torch.nn.functional.softmax(logits, dim=-1)
        confidence, pred_idx = self.torch.max(probs, dim=-1)
        
        label = self.classes[pred_idx.item()]
        label = label.lower().replace(" ", "_")
        
        return {
            "label": label,
            "confidence": float(confidence),
            "all_probs": {self.classes[i]: float(probs[0][i]) for i in range(len(self.classes))}
        }

class CoughInference:
    def __init__(self):
        try:
            import torch
            from transformers import AutoFeatureExtractor
            from safetensors.torch import load_file
            from .cough_model_logic.models import ASTAudioClassifier
            self.torch = torch
            self.feature_extractor = AutoFeatureExtractor.from_pretrained(COUGH_MODEL_PATH)
            self.model = ASTAudioClassifier() 
            
            weights_path = os.path.join(COUGH_MODEL_PATH, "model.safetensors")
            if os.path.exists(weights_path):
                raw_weights = load_file(weights_path)
                mapped_weights = {
                    k.replace("audio_spectrogram_transformer", "ast"): v
                    for k, v in raw_weights.items()
                }
                self.model.load_state_dict(mapped_weights, strict=False)
                self.model.eval()
            
            with open(os.path.join(COUGH_MODEL_PATH, "config.json")) as f:
                config = json.load(f)
                self.classes = config.get("id2label", {})
                
        except Exception as e:
            self.model = None
            self.classes = {}


    def predict(self, audio_path: str) -> Dict[str, Any]:
        if not self.model or not os.path.exists(audio_path):
            return {"error": "Model not loaded or file missing", "label": "uncertain", "confidence": 0.0}
        
        try:
            import librosa
            # sr=16000 is critical for AST models
            y, sr = librosa.load(audio_path, sr=16000)
            
            if len(y) == 0:
                raise ValueError("Loaded audio is empty")
                
            inputs = self.feature_extractor(y, sampling_rate=16000, return_tensors="pt")
            
            with self.torch.no_grad():
                logits = self.model(inputs["input_values"])
                prob = self.torch.sigmoid(logits)
                conf = float(prob.item())
                
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
