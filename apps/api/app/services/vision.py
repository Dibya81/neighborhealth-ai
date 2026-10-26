"""Does a report photo actually show a possible mosquito breeding site?

Zero-shot CLIP: compare the image with text prompts for breeding sites vs. common junk uploads
(selfies, screenshots, documents...). No training data needed to start; measure it with
`scripts/eval_vision.py` on a folder of labelled photos, then tune THRESHOLDS from that report.
If transformers/torch aren't installed (or VISION_ENABLED=false) every photo goes to human review.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from app.settings import get_settings

POSITIVE = [
    "a photo of stagnant water on the ground",
    "a photo of a discarded tyre holding rain water",
    "a photo of an uncovered water drum or bucket",
    "a photo of a blocked drain with standing water",
    "a photo of garbage with plastic containers and cups that hold water",
    "a photo of a flower pot tray or cooler with water",
    "a photo of a construction site with water puddles",
]
NEGATIVE = [
    "a selfie of a person's face",
    "a screenshot of a phone screen",
    "a photo of a document or printed text",
    "a photo of food on a plate",
    "a photo of a clean dry road",
    "a photo of a room interior",
    "a blank or completely dark photo",
]
THRESHOLDS = {"likely": 0.60, "unlikely": 0.35}
MODEL_ID = "openai/clip-vit-base-patch32"


@dataclass
class VisionResult:
    label: str          # likely_breeding_site | uncertain | unlikely | unavailable
    score: float | None
    top_prompt: str | None = None


class VisionChecker:
    _lock = threading.Lock()
    _model = None
    _processor = None

    def _load(self) -> bool:
        if not get_settings().vision_enabled:
            return False
        with self._lock:
            if VisionChecker._model is None:
                try:
                    from transformers import CLIPModel, CLIPProcessor
                except ImportError:
                    return False
                VisionChecker._model = CLIPModel.from_pretrained(MODEL_ID).eval()
                VisionChecker._processor = CLIPProcessor.from_pretrained(MODEL_ID)
        return True

    def check(self, image) -> VisionResult:
        if not self._load():
            return VisionResult("unavailable", None)
        import torch
        prompts = POSITIVE + NEGATIVE
        inputs = self._processor(text=prompts, images=image.convert("RGB"), return_tensors="pt", padding=True)
        with torch.no_grad():
            probs = self._model(**inputs).logits_per_image.softmax(dim=-1)[0]
        p_pos = float(probs[: len(POSITIVE)].sum())
        top = prompts[int(probs.argmax())]
        label = ("likely_breeding_site" if p_pos >= THRESHOLDS["likely"]
                 else "unlikely" if p_pos < THRESHOLDS["unlikely"] else "uncertain")
        return VisionResult(label, round(p_pos, 4), top)


vision = VisionChecker()
