"""Measure how often LLM ward explanations stay faithful to the model's numbers.

    python scripts/eval_explanations.py            # all wards, horizon 1, English
Writes docs/v2/explanation_eval.md: verifier pass rate and the most common problems.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.forecast_store import get_bundle  # noqa: E402
from app.services.assistant.explain import explain_ward  # noqa: E402
from pipeline.config import REPO_ROOT  # noqa: E402


def main(limit: int | None = None) -> None:
    b = get_bundle()
    if not b:
        raise SystemExit("publish a forecast first: python -m ml weekly")
    wards = [w["ward_id"] for w in b["wards"]["1"]][:limit]
    passed, llm_used, problems = 0, 0, Counter()
    for wid in wards:
        out = explain_ward(wid, 1, "en")
        if out["method"].startswith("llm") or "failed" in out["method"]:
            llm_used += 1
        if out["method"] == "llm":
            passed += 1
        for p in out["verification_problems"]:
            problems[p.split(" ")[0] + " " + p.split(" ")[1]] += 1
    rate = passed / llm_used if llm_used else None
    lines = ["# Ward explanation faithfulness", "", f"Wards evaluated: {len(wards)}",
             f"LLM explanations generated: {llm_used}",
             f"Passed verification (no invented numbers or drivers): {rate:.1%}" if rate is not None else "LLM not configured",
             "", "Most common problems:", *[f"- {k}: {v}" for k, v in problems.most_common(10)]]
    out = REPO_ROOT / "docs" / "v2" / "explanation_eval.md"
    out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
