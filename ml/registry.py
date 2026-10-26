"""A small, file-based model registry with champion/challenger promotion.

data/v2/models/
    registry.json                   {"champion": "<version>", "history": [...]}
    <version>/metadata.json         model type, data range, scores, git sha, file hashes
    <version>/scores.csv            backtest scores (all models, all horizons)
    <version>/backtest.csv          every backtest prediction (for intervals + audits)
    <version>/h1.txt ...            LightGBM native model files (no pickle) when available
If MLflow is installed and MLFLOW_TRACKING_URI is set, every run is also logged there.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from pipeline.config import REPO_ROOT, get_paths

GATE_MIN_SKILL = 0.0          # must beat seasonal naive on MAE (averaged over horizons)
GATE_COVERAGE80 = (0.65, 0.95)  # 80% intervals must cover roughly 80% of outcomes


def models_dir() -> Path:
    d = get_paths().root / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _registry_path() -> Path:
    return models_dir() / "registry.json"


def load_registry() -> dict:
    p = _registry_path()
    return json.loads(p.read_text()) if p.exists() else {"champion": None, "history": []}


def champion_metadata() -> dict | None:
    reg = load_registry()
    if not reg["champion"]:
        return None
    return json.loads((models_dir() / reg["champion"] / "metadata.json").read_text())


def _git_sha() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return None


def summarise(scores: pd.DataFrame, model: str) -> dict:
    s = scores[scores["model"] == model]
    out = {"mae": float(s["mae"].mean()), "skill_vs_seasonal_naive": float(s["skill_vs_seasonal_naive"].mean())}
    if "wis" in s and s["wis"].notna().any():
        out["wis"] = float(s["wis"].mean())
    if "coverage80" in s and s["coverage80"].notna().any():
        out["coverage80"] = float(s["coverage80"].mean())
        out["coverage50"] = float(s["coverage50"].mean())
        out["coverage95"] = float(s["coverage95"].mean())
    return out


def quality_gate(summary: dict) -> tuple[bool, list[str]]:
    reasons = []
    if not summary.get("skill_vs_seasonal_naive", -1) > GATE_MIN_SKILL:
        reasons.append(f"does not beat seasonal naive (skill {summary.get('skill_vs_seasonal_naive'):.3f})")
    cov = summary.get("coverage80")
    if cov is not None and not (GATE_COVERAGE80[0] <= cov <= GATE_COVERAGE80[1]):
        reasons.append(f"80% interval coverage {cov:.2f} outside {GATE_COVERAGE80}")
    return (not reasons), reasons


def register_candidate(model_type: str, scores: pd.DataFrame, backtest: pd.DataFrame, fitted: dict,
                       data_info: dict) -> str:
    version = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + f"-{model_type}"
    d = models_dir() / version
    d.mkdir(parents=True)
    scores.to_csv(d / "scores.csv", index=False)
    backtest.to_csv(d / "backtest.csv", index=False)
    files = {}
    for h, model in fitted.items():
        m = getattr(model, "model", None)
        if m is not None and hasattr(m, "booster_"):  # LightGBM: native text format, no pickle
            p = d / f"h{h}.txt"
            m.booster_.save_model(str(p))
            files[f"h{h}"] = {"path": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
    meta = {"version": version, "model_type": model_type, "created_at": datetime.now(timezone.utc).isoformat(),
            "git_sha": _git_sha(), "data": data_info, "summary": summarise(scores, model_type), "files": files,
            "note": "Non-LightGBM models are refit from data at publish time (deterministic, seeded)."}
    (d / "metadata.json").write_text(json.dumps(meta, indent=2, default=str))
    _log_mlflow(meta, scores)
    return version


def decide_promotion(candidate_version: str, scores: pd.DataFrame) -> dict:
    """Promote the candidate if it passes the quality gate and is at least as good as the current
    champion's model type *re-evaluated on the same data* (fair comparison)."""
    reg = load_registry()
    cand = json.loads((models_dir() / candidate_version / "metadata.json").read_text())
    ok, reasons = quality_gate(cand["summary"])
    decision = {"candidate": candidate_version, "at": datetime.now(timezone.utc).isoformat()}
    if not ok:
        decision.update(promoted=False, reason="; ".join(reasons))
    elif reg["champion"] is None:
        decision.update(promoted=True, reason="first model to pass the quality gate")
    else:
        champ = json.loads((models_dir() / reg["champion"] / "metadata.json").read_text())
        champ_now = summarise(scores, champ["model_type"]) if champ["model_type"] in set(scores["model"]) else champ["summary"]
        key = "wis" if "wis" in cand["summary"] and "wis" in champ_now else "mae"
        better = cand["summary"][key] <= champ_now[key] * 1.0001
        decision.update(promoted=better, reason=f"{key}: candidate {cand['summary'][key]:.2f} vs champion "
                                                 f"{champ['model_type']} {champ_now[key]:.2f} on the same backtest")
    if decision["promoted"]:
        reg["champion"] = candidate_version
    reg["history"].append(decision)
    _registry_path().write_text(json.dumps(reg, indent=2))
    return decision


def rollback() -> str | None:
    """Make the previous promoted version champion again."""
    reg = load_registry()
    promoted = [h["candidate"] for h in reg["history"] if h.get("promoted")]
    if len(promoted) < 2:
        return None
    reg["champion"] = promoted[-2]
    reg["history"].append({"candidate": promoted[-2], "promoted": True, "reason": "manual rollback",
                           "at": datetime.now(timezone.utc).isoformat()})
    _registry_path().write_text(json.dumps(reg, indent=2))
    return reg["champion"]


def _log_mlflow(meta: dict, scores: pd.DataFrame) -> None:
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        return
    try:
        import mlflow
    except ImportError:
        return
    mlflow.set_experiment("neighborhealth-forecast")
    with mlflow.start_run(run_name=meta["version"]):
        mlflow.log_params({"model_type": meta["model_type"], **{f"data_{k}": v for k, v in meta["data"].items()}})
        mlflow.log_metrics({k: v for k, v in meta["summary"].items() if isinstance(v, float)})
        for _, r in scores.iterrows():
            mlflow.log_metric(f"{r['model']}_h{r['horizon']}_mae", float(r["mae"]))
