"""Measure extraction accuracy against the hand-labelled gold set and write a report.

Metrics per extractor and field:
  * accuracy  = exact matches / gold values that exist
  * coverage  = predictions that exist / gold values that exist
  * false_presence = predictions made where the gold says "not in the PDF"
Plus a validator check: accuracy of rows the validator trusted vs rows it flagged. If trusted
rows are much more accurate, the validator is doing its job and reconciliation is justified.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pandas as pd

from pipeline.config import REPO_ROOT, get_paths
from pipeline.eval.gold import GOLD_FIELDS, field_key, load_gold
from pipeline.extract.schema import Bulletin
from pipeline.validate.checks import check_bulletin, is_trustworthy


def _pred(b: Bulletin | None, area: str, section: str, name: str):
    if b is None:
        return None
    row = b.get(area)
    if row is None:
        return None
    counts = row.on_day if section == "day" else row.cumulative
    return getattr(counts, name) if counts else None


def load_extractions(name: str) -> dict[str, Bulletin]:
    p = get_paths().interim / f"extracted_{name}.jsonl"
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        if line.strip():
            b = Bulletin.model_validate_json(line)
            out[b.report_date.isoformat()] = b
    return out


def evaluate() -> dict:
    gold = load_gold()
    if not gold:
        raise SystemExit("No gold labels yet. Run: python -m pipeline label")
    results: dict = {"n_bulletins_labelled": len(gold), "extractors": {}}
    reconciled_path = get_paths().processed / "bulletin_rows.csv"
    reconciled = pd.read_csv(reconciled_path, parse_dates=["date"]) if reconciled_path.exists() else None

    for ext in ("rule", "llm", "reconciled"):
        if ext == "reconciled":
            if reconciled is None:
                continue
            preds = {}
            for iso in gold:
                sub = reconciled[reconciled["date"] == pd.Timestamp(iso)]
                preds[iso] = {field_key(a, s, n): (None if sub[sub["area"] == a].empty or pd.isna(sub[sub["area"] == a].iloc[0][f"{s}_{n}"])
                                                   else int(sub[sub["area"] == a].iloc[0][f"{s}_{n}"]))
                              for a, s, n in GOLD_FIELDS}
        else:
            bulletins = load_extractions(ext)
            if not bulletins:
                continue
            preds = {iso: {field_key(a, s, n): _pred(bulletins.get(iso), a, s, n) for a, s, n in GOLD_FIELDS} for iso in gold}

        per_field = {}
        trusted_hits = defaultdict(lambda: [0, 0])  # trusted?: [correct, total]
        for a, s, n in GOLD_FIELDS:
            k = field_key(a, s, n)
            n_gold = correct = covered = false_presence = 0
            for iso, rec in gold.items():
                g = rec["fields"].get(k, "missing")
                if g == "missing":
                    continue
                p = preds[iso][k]
                if g is None:
                    false_presence += p is not None
                    continue
                n_gold += 1
                covered += p is not None
                correct += p == g
            per_field[k] = {"n": n_gold, "accuracy": round(correct / n_gold, 4) if n_gold else None,
                            "coverage": round(covered / n_gold, 4) if n_gold else None,
                            "false_presence": false_presence}
        if ext in ("rule", "llm"):
            bulletins = load_extractions(ext)
            for iso, rec in gold.items():
                b = bulletins.get(iso)
                if not b:
                    continue
                flags = check_bulletin(b)
                for a, s, n in GOLD_FIELDS:
                    g = rec["fields"].get(field_key(a, s, n))
                    if g is None:
                        continue
                    trusted = is_trustworthy(flags.get(a, ["missing"])) and b.get(a) is not None
                    trusted_hits[trusted][0] += _pred(b, a, s, n) == g
                    trusted_hits[trusted][1] += 1
        overall_n = sum(v["n"] for v in per_field.values())
        overall_c = sum((v["accuracy"] or 0) * v["n"] for v in per_field.values())
        results["extractors"][ext] = {
            "overall_accuracy": round(overall_c / overall_n, 4) if overall_n else None,
            "fields": per_field,
            "validator": {("trusted" if t else "flagged"): {"accuracy": round(c / tot, 4) if tot else None, "n": tot}
                          for t, (c, tot) in trusted_hits.items()},
        }
    _write_report(results)
    return results


def _write_report(results: dict) -> None:
    out_dir = REPO_ROOT / "docs" / "v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "extraction_eval.json").write_text(json.dumps(results, indent=2))
    lines = ["# Bulletin extraction: accuracy report", "",
             f"Hand-labelled bulletins: **{results['n_bulletins_labelled']}**", "",
             "| Extractor | Overall accuracy | " + " | ".join(field_key(*f) for f in GOLD_FIELDS) + " |",
             "|---|---|" + "---|" * len(GOLD_FIELDS)]
    for ext, r in results["extractors"].items():
        cells = []
        for f in GOLD_FIELDS:
            v = r["fields"][field_key(*f)]
            cells.append("n/a" if v["accuracy"] is None else f"{v['accuracy']:.0%} (cov {v['coverage']:.0%})")
        lines.append(f"| {ext} | {r['overall_accuracy']:.1%} | " + " | ".join(cells) + " |"
                     if r["overall_accuracy"] is not None else f"| {ext} | n/a |")
    lines += ["", "## Does the validator work?", "",
              "Accuracy of rows the validator trusted vs. rows it flagged (higher gap = more useful validator).", ""]
    for ext, r in results["extractors"].items():
        if r.get("validator"):
            lines.append(f"- **{ext}**: " + ", ".join(f"{k}: {v['accuracy']:.0%} (n={v['n']})"
                                                         for k, v in r["validator"].items() if v["accuracy"] is not None))
    (out_dir / "extraction_eval.md").write_text("\n".join(lines) + "\n")
