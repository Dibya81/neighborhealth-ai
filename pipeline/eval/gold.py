"""Hand-labelled gold set: the ground truth used to measure extraction accuracy.

You (a human) open each sampled PDF and type the true values for a handful of key fields.
This is the only way to know how accurate the extractors really are.
"""
from __future__ import annotations

import json
import platform
import random
import subprocess
from collections import defaultdict
from datetime import date
from pathlib import Path

from pipeline.config import get_paths
from pipeline.sources.icts_bulletins import available_bulletins

# (area, section, field). These are the fields the forecasting step depends on.
GOLD_FIELDS = [
    ("BBMP", "day", "total_pos"),
    ("BBMP", "cum", "total_pos"),
    ("BBMP", "cum", "samples"),
    ("BBMP", "cum", "deaths"),
    ("Bengaluru Urban", "cum", "total_pos"),
    ("STATE_TOTAL", "cum", "total_pos"),
]

PROMPTS = {
    ("BBMP", "day", "total_pos"): "BBMP: positives ON THE DAY (Total +ves)",
    ("BBMP", "cum", "total_pos"): "BBMP: CUMULATIVE positives (Total +ves)",
    ("BBMP", "cum", "samples"): "BBMP: CUMULATIVE blood samples tested",
    ("BBMP", "cum", "deaths"): "BBMP: CUMULATIVE deaths",
    ("Bengaluru Urban", "cum", "total_pos"): "Bangaluru (U) district: CUMULATIVE positives",
    ("STATE_TOTAL", "cum", "total_pos"): "STATE TOTAL: CUMULATIVE positives",
}


def field_key(area: str, section: str, name: str) -> str:
    return f"{area}.{section}.{name}"


def gold_file() -> Path:
    return get_paths().gold / "labels.jsonl"


def load_gold() -> dict[str, dict]:
    p = gold_file()
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["date"]] = rec
    return out


def sample_dates(n: int, seed: int = 42) -> list[tuple[date, Path]]:
    """Stratified by year so every year's format is represented."""
    by_year: dict[int, list] = defaultdict(list)
    for d, p in available_bulletins():
        by_year[d.year].append((d, p))
    rng = random.Random(seed)
    years = sorted(by_year)
    if not years:
        return []
    per_year = max(1, n // len(years))
    picked = []
    for y in years:
        items = by_year[y][:]
        rng.shuffle(items)
        picked += items[:per_year]
    return sorted(picked)[:n]


def _open(path: Path) -> None:
    try:
        cmd = {"Darwin": ["open"], "Windows": ["cmd", "/c", "start", ""]}.get(platform.system(), ["xdg-open"])
        subprocess.Popen(cmd + [str(path)])
    except Exception:
        pass


def label_interactive(n: int = 40, labeller: str = "me") -> None:
    gold = load_gold()
    todo = [(d, p) for d, p in sample_dates(n) if d.isoformat() not in gold]
    print(f"{len(gold)} already labelled, {len(todo)} to go. Enter a number, '-' if not in the PDF, "
          f"'s' to skip this bulletin, 'q' to quit (progress is saved after every bulletin).\n")
    for d, p in todo:
        print(f"=== {d}  ({p})")
        _open(p)
        values: dict[str, int | None] = {}
        skip = False
        for key in GOLD_FIELDS:
            while True:
                ans = input(f"  {PROMPTS[key]}: ").strip().lower()
                if ans == "q":
                    return
                if ans == "s":
                    skip = True
                    break
                if ans == "-":
                    values[field_key(*key)] = None
                    break
                if ans.replace(",", "").isdigit():
                    values[field_key(*key)] = int(ans.replace(",", ""))
                    break
                print("    please type a whole number, '-', 's' or 'q'")
            if skip:
                break
        if skip:
            continue
        notes = input("  notes (optional): ").strip()
        with open(gold_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps({"date": d.isoformat(), "fields": values, "labeller": labeller, "notes": notes}) + "\n")
