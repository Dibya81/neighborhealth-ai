"""Evaluate the zero-shot photo check on YOUR labelled photos.

Folder layout:
    photos/positive/*.jpg   real breeding sites (standing water, tyres, containers...)
    photos/negative/*.jpg   everything else people might upload

    VISION_ENABLED=true python scripts/eval_vision.py photos/
Prints precision/recall at several thresholds so you can set THRESHOLDS in app/services/vision.py.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("VISION_ENABLED", "true")

from PIL import Image  # noqa: E402

from app.services.vision import vision  # noqa: E402


def main(root: str) -> None:
    rows = []
    for label in ("positive", "negative"):
        for p in sorted(Path(root, label).glob("*")):
            if p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            r = vision.check(Image.open(p))
            if r.score is None:
                raise SystemExit("Vision model unavailable: pip install transformers torch")
            rows.append((label == "positive", r.score))
    print(f"{len(rows)} photos ({sum(y for y, _ in rows)} positive)")
    print("threshold  precision  recall  flagged_for_review")
    for th in (0.3, 0.4, 0.5, 0.6, 0.7):
        tp = sum(1 for y, s in rows if y and s >= th)
        fp = sum(1 for y, s in rows if not y and s >= th)
        fn = sum(1 for y, s in rows if y and s < th)
        prec = tp / (tp + fp) if tp + fp else 0
        rec = tp / (tp + fn) if tp + fn else 0
        print(f"{th:9.2f}  {prec:9.2%}  {rec:6.2%}  {sum(1 for _, s in rows if s < th):5d}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "photos")
