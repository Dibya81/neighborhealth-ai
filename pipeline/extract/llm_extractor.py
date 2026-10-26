"""LLM-based extractor: layout-preserving PDF text -> strict JSON -> validated Bulletin.

Why have this at all when there's a rule-based parser? Government PDFs drift in format and
pdf text extraction scrambles rows. The LLM reads the table the way a human would. The eval
step (pipeline.eval) measures which extractor is actually more accurate on hand-labelled
bulletins, and the reconciler uses the validator to decide per row. Neither is trusted blindly.

Uses OpenRouter's OpenAI-compatible API (same provider as v1). Responses are cached on disk by
(pdf hash, prompt version, model) so re-runs are free and results are reproducible.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request
from datetime import date
from pathlib import Path

import pdfplumber

from pipeline.config import canonical_area, get_paths
from pipeline.extract.schema import AreaRow, Bulletin, Counts

PROMPT_VERSION = "v1"
DEFAULT_MODEL = os.environ.get("NH_EXTRACT_MODEL", "google/gemini-2.0-flash-001")
API_URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You extract numbers from Karnataka NVBDCP "Daily Report of Dengue" bulletins.
The PDF text below was extracted with layout preserved; columns may be misaligned.
The bulletin can also contain a Chikungunya table: IGNORE it completely.

Dengue table columns per district row, in order:
SL, District, Total blocks (taluks) in district,
[affected] Taluks, PHC, Villages, Population of affected villages,
[on the day] Suspected cases, Blood samples tested, IgM MAC ELISA positive, NS1 antigen (or Others) positive, Total positives, Deaths,
[cumulative from 1 January] Suspected cases, Blood samples tested, IgM MAC ELISA positive, NS1 antigen (or Others) positive, Total positives, Deaths.
The "Bangaluru City (BBMP)" row has no blocks value. The state total row has no district name.
Sometimes a row's label is missing or its cumulative numbers are on the next line.

Rules:
- Copy numbers exactly as printed. Never compute, guess or fill in a number. Use null if unreadable.
- Arithmetic hint for checking yourself: IgM + NS1 = Total positives.
- Return ONLY JSON matching this shape:
{"printed_date": "string or null", "rows": [
  {"district": "name as printed, or 'STATE_TOTAL', or 'BBMP'",
   "label_was_missing": false,
   "on_day": {"suspected": int|null, "samples": int|null, "igm": int|null, "ns1": int|null, "total_pos": int|null, "deaths": int|null},
   "cumulative": {"suspected": ..., "samples": ..., "igm": ..., "ns1": ..., "total_pos": ..., "deaths": ...} or null}
]}"""


def layout_text(pdf_path: Path, max_chars: int = 24000) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        pages = [p.extract_text(layout=True) or "" for p in pdf.pages]
    text = "\n\n=== PAGE BREAK ===\n\n".join(pages)
    return text[:max_chars]


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        env = Path(__file__).resolve().parents[2] / "backend" / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("OPENROUTER_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"')
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY not set (env var or backend/.env)")
    return key


def _call_llm(text: str, model: str, retries: int = 3) -> str:
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": text}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
        "X-Title": "NeighborHealth bulletin extraction",
    })
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
        except Exception as e:  # rate limits / transient errors
            last_err = e
            time.sleep(2 ** attempt * 2)
    raise RuntimeError(f"LLM call failed after {retries} attempts: {last_err}")


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        s = s.rsplit("```", 1)[0]
    return s


def extract_llm(pdf_path: Path, report_date: date, model: str = DEFAULT_MODEL) -> Bulletin:
    pdf_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:16]
    cache_key = hashlib.sha256(f"{pdf_hash}|{PROMPT_VERSION}|{model}".encode()).hexdigest()[:24]
    cache_file = get_paths().llm_cache / f"{cache_key}.json"

    if cache_file.exists():
        raw = cache_file.read_text()
    else:
        raw = _call_llm(layout_text(pdf_path), model)
        cache_file.write_text(raw)

    warnings: list[str] = []
    try:
        data = json.loads(_strip_fences(raw))
    except json.JSONDecodeError:
        return Bulletin(report_date=report_date, extractor="llm", warnings=["invalid JSON from LLM"],
                        source_file=str(pdf_path))

    rows: list[AreaRow] = []
    seen: set[str] = set()
    for r in data.get("rows", []):
        name = (r.get("district") or "").strip()
        area = "STATE_TOTAL" if name.upper() in ("STATE_TOTAL", "TOTAL") else canonical_area(name)
        if not area or area in seen:
            continue
        seen.add(area)
        try:
            on_day = Counts(**(r.get("on_day") or {}))
            cum = Counts(**r["cumulative"]) if r.get("cumulative") else None
        except Exception as e:
            warnings.append(f"{area}: bad counts ({e.__class__.__name__})")
            continue
        rows.append(AreaRow(area=area, raw_label=name or None,
                            inferred_label=bool(r.get("label_was_missing")), on_day=on_day, cumulative=cum))
    if not any(r.area == "BBMP" for r in rows):
        warnings.append("BBMP row not found")
    return Bulletin(report_date=report_date, printed_date=data.get("printed_date"), extractor="llm",
                    rows=rows, warnings=warnings, source_file=str(pdf_path))
