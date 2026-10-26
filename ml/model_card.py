"""Generate docs/v2/MODEL_CARD.md from the latest backtest and registry: the numbers are never typed by hand."""
from __future__ import annotations

import json

import pandas as pd

from ml.registry import champion_metadata, load_registry
from pipeline.config import REPO_ROOT, get_paths


def write_model_card() -> str:
    scores_p = get_paths().processed / "backtest_scores.csv"
    champ = champion_metadata()
    lines = ["# Model card: BBMP weekly dengue forecast", ""]
    lines += ["**Task:** forecast weekly lab-confirmed dengue cases reported for BBMP, 1–4 weeks ahead, "
              "with 50/80/95% prediction intervals.", "",
              "**Evaluation:** rolling-origin backtest (train on weeks ≤ t, predict t+h, slide forward 1 week). "
              "Intervals are online conformal, using only residuals already observable at each origin.", ""]
    if champ:
        lines += [f"**Champion:** `{champ['model_type']}` (version `{champ['version']}`, data "
                  f"{champ['data']['first_week']} → {champ['data']['last_week']}, {champ['data']['n_weeks']} weeks)", "",
                  "```json", json.dumps(champ["summary"], indent=2), "```", ""]
    else:
        lines += ["**Champion:** none yet (no model has passed the quality gate).", ""]
    if scores_p.exists():
        s = pd.read_csv(scores_p)
        cols = [c for c in ["model", "horizon", "mae", "wis", "coverage50", "coverage80", "coverage95",
                            "skill_vs_seasonal_naive", "n"] if c in s]
        lines += ["## Backtest results (all models)", "",
                  "Skill = 1 − MAE / MAE(seasonal naive). Positive means better than the baseline.", ""]
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "---|" * len(cols))
        for _, r in s[cols].iterrows():
            lines.append("| " + " | ".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in r.values) + " |")
        lines.append("")
    reg = load_registry()
    if reg["history"]:
        lines += ["## Promotion history", ""]
        for h in reg["history"][-10:]:
            lines.append(f"- {h.get('at', '')[:19]} `{h['candidate']}`: {'PROMOTED' if h.get('promoted') else 'rejected'}"
                         f" ({h.get('reason', '')})")
        lines.append("")
    lines += ["## Limitations", "",
              "- Targets are *reported* cases: they depend on testing volume and reporting delays.",
              "- One weather point for the whole city.",
              "- Ward values in the app are allocations of the city forecast (population × risk factors), "
              "not ward-level predictions learned from ward data.", ""]
    out = REPO_ROOT / "docs" / "v2" / "MODEL_CARD.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
    return str(out)
