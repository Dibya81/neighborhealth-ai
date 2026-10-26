"""Rule-based extractor for Karnataka NVBDCP daily dengue bulletins.

Observed layout (2022-2024), one row per district:
    SL  District  Blocks | Taluks PHC Villages Population(affected) |
        ON THE DAY: Suspected Samples IgM NS1 Total+ Deaths |
        CUMULATIVE (from 1 Jan): Suspected Samples IgM NS1 Total+ Deaths
The BBMP row has no "Blocks" value. The state-total row has no label.

Real-world mess this parser has to survive (seen in actual bulletins):
  * PDF text order is unreliable; the dengue and chikungunya tables can interleave.
  * Some rows lose their label (e.g. the BBMP row appears as bare numbers).
  * Cumulative cells sometimes land on a separate text line.
So instead of trusting positions blindly, every candidate interpretation of a row is scored with
arithmetic self-consistency checks (IgM + NS1 == Total, Total <= Samples) and the best one wins.
Anything uncertain is recorded in `warnings` so the validator and the evaluation can see it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import pdfplumber

from pipeline.config import canonical_area
from pipeline.extract.schema import COUNT_FIELDS, AreaRow, Bulletin, Counts

NUM_RE = re.compile(r"^\d[\d,]*$")
TITLE_RE = re.compile(r"Daily\s+Report\s+of\s+(Dengue|Chikungunya)", re.IGNORECASE)
DATE_RE = re.compile(r"Date\s*:?\s*(\d{1,2})\s*-\s*(\d{1,2})\s*-\s*(\d{4})?")
YEAR_RE = re.compile(r"(?:Karnataka\s+State\s*-\s*|NVBDCP/HS/2\s*\(1\)\s*/\s*)(\d{4})", re.IGNORECASE)
LINE_TOLERANCE = 3.0  # points; words whose tops are this close belong to the same text line


# ---------------------------------------------------------------- line reconstruction
@dataclass
class Line:
    page: int
    top: float
    section: str           # "dengue" | "chikungunya" | "unknown"
    text: str
    label: str = ""
    numbers: list[int] = field(default_factory=list)
    num_x1: list[float] = field(default_factory=list)   # right edge of each number (column position)


def _split_tokens(words: list[dict]) -> tuple[str, list[int], list[float]]:
    """Return (label, numbers, number right-edges). A leading serial number before the label is dropped."""
    tokens = [w["text"] for w in words]
    start = 1 if len(tokens) >= 2 and NUM_RE.match(tokens[0]) and not NUM_RE.match(tokens[1]) else 0
    label_tokens: list[str] = []
    numbers: list[int] = []
    x1s: list[float] = []
    for w in words[start:]:
        tok = w["text"]
        if NUM_RE.match(tok):
            numbers.append(int(tok.replace(",", "")))
            x1s.append(w["x1"])
        else:
            if numbers:  # text after the numbers (footnotes etc.): stop here
                break
            label_tokens.append(tok)
    return " ".join(label_tokens), numbers, x1s


def _drop_overprinted(words: list[dict], tol: float = 2.0) -> list[dict]:
    """Some rows are printed twice on top of each other (seen on Gadag rows), which would double
    every number in the row. Keep one copy of any word that has an identical twin at the same spot."""
    kept: list[dict] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if any(k["text"] == w["text"] and abs(k["x0"] - w["x0"]) <= tol and abs(k["top"] - w["top"]) <= tol
               for k in kept[-40:]):
            continue
        kept.append(w)
    return kept


def read_lines(pdf_path: Path) -> list[Line]:
    lines: list[Line] = []
    current_section = "unknown"
    with pdfplumber.open(pdf_path) as pdf:
        for pno, page in enumerate(pdf.pages):
            # Section boundaries on this page, by vertical position of the titles.
            titles = sorted(
                ((m["top"], m["groups"][0].lower()) for m in page.search(TITLE_RE.pattern, regex=True, case=False)),
                key=lambda t: t[0],
            )
            words = page.extract_words(x_tolerance=1.5, y_tolerance=LINE_TOLERANCE, keep_blank_chars=False)
            # Sort by exact top: rounding first can split one table row across two clusters
            # when its words sit on either side of a rounding boundary (seen in real bulletins).
            words = [w for w in words if w.get("upright", True)]  # drop rotated margin footnotes
            words = _drop_overprinted(words)
            words.sort(key=lambda w: w["top"])
            clusters: list[list[dict]] = []
            for w in words:
                if clusters and abs(w["top"] - clusters[-1][0]["top"]) <= LINE_TOLERANCE:
                    clusters[-1].append(w)
                else:
                    clusters.append([w])
            for cl in clusters:
                cl.sort(key=lambda w: w["x0"])
                top = cl[0]["top"]
                section = current_section
                for t_top, t_name in titles:
                    if t_top <= top + LINE_TOLERANCE:
                        section = t_name
                text = " ".join(w["text"] for w in cl)
                label, numbers, x1s = _split_tokens(cl)
                lines.append(Line(pno, top, section, text, label, numbers, x1s))
            if titles:
                current_section = titles[-1][1]
    return lines


# ---------------------------------------------------------------- row interpretation
def _group_ok(g: list[int]) -> bool:
    """Arithmetic self-consistency of one 6-number count group."""
    if len(g) != 6:
        return False
    _susp, samples, igm, ns1, total, _deaths = g
    return igm + ns1 == total and (samples == 0 or total <= samples)


def interpret_numbers(nums: list[int]) -> tuple[Optional[dict], list[str]]:
    """Choose the most self-consistent reading of a row's numbers.

    Returns a dict with prefix fields + on_day (+ cumulative) or None, and warnings.
    """
    warnings: list[str] = []
    n = len(nums)
    candidates = []
    if n >= 16:
        k = n - 12
        candidates.append((k, True, _group_ok(nums[k:k + 6]) + _group_ok(nums[k + 6:k + 12])))
    if n >= 10:
        k = n - 6
        candidates.append((k, False, _group_ok(nums[k:k + 6]) * 1.0))
    if not candidates:
        return None, [f"too few numbers ({n})"]

    def prefix_bonus(k: int) -> float:
        return 0.5 if k in (4, 5) else 0.0

    k, has_cum, score = max(candidates, key=lambda c: (c[2] + prefix_bonus(c[0]), c[1]))
    if score == 0:
        warnings.append("no self-consistent reading; values may be misaligned")
    prefix = nums[:k]
    out: dict = {}
    if len(prefix) >= 5:
        out["blocks"] = prefix[-5]
    if len(prefix) >= 4:
        out.update(taluks_affected=prefix[-4], phc_affected=prefix[-3],
                   villages_affected=prefix[-2], population_affected=prefix[-1])
    if len(prefix) not in (4, 5):
        warnings.append(f"unexpected prefix length {len(prefix)}")
    out["on_day"] = Counts.from_list(nums[k:k + 6])
    out["cumulative"] = Counts.from_list(nums[k + 6:k + 12]) if has_cum else None
    return out, warnings


COLUMN_FIELDS = ["blocks", "taluks_affected", "phc_affected", "villages_affected", "population_affected"]
N_COLUMNS = 5 + 6 + 6   # prefix + on-day counts + cumulative counts


def column_anchors(lines: list[Line]) -> dict[int, list[float]]:
    """Per page: the x position (right edge) of each of the 17 numeric columns.

    The state-total row is always fully populated, so its 17 numbers are exactly one per column.
    Measuring them on the page itself keeps the parser valid when the layout shifts between years.
    """
    out: dict[int, list[float]] = {}
    for l in lines:
        if l.section == "dengue" and l.label.lower().startswith("total") and len(l.numbers) == N_COLUMNS:
            out.setdefault(l.page, list(l.num_x1))
    return out


def interpret_by_position(line: Line, anchors: list[float]) -> tuple[Optional[dict], list[str]]:
    """Assign each number in a row to its nearest column.

    Real bulletins leave cells blank all the time: the whole 'on the day' block on most rows, the
    deaths cell on some, the blocks cell on the BBMP row. Counting numbers cannot tell which cell
    is blank; column position can. Returns None if two numbers compete for one column.
    """
    slots: dict[int, int] = {}
    for n, x in zip(line.numbers, line.num_x1):
        j = min(range(len(anchors)), key=lambda c: abs(anchors[c] - x))
        if j in slots:
            return None, [f"position split ambiguous (two numbers in column {j})"]
        slots[j] = n
    day = [slots.get(5 + i) for i in range(6)]
    cum = [slots.get(11 + i) for i in range(6)]
    out: dict = {f: slots.get(i) for i, f in enumerate(COLUMN_FIELDS)}
    out["on_day"] = Counts(**dict(zip(COUNT_FIELDS, day)))
    out["cumulative"] = Counts(**dict(zip(COUNT_FIELDS, cum))) if any(v is not None for v in cum) else None
    return out, []


def _is_cumulative_continuation(line: Line) -> bool:
    return not line.label and len(line.numbers) == 6 and _group_ok(line.numbers)


# ---------------------------------------------------------------- main entry point
def has_text_layer(pdf_path: Path) -> bool:
    with pdfplumber.open(pdf_path) as pdf:
        return len(pdf.pages[0].extract_words()) >= 50


def parse_bulletin(pdf_path: Path, report_date: date) -> Bulletin:
    if not has_text_layer(pdf_path):   # scanned image: no text to parse, so OCR the two rows we need
        from pipeline.extract.ocr_extractor import extract_scan
        return extract_scan(pdf_path, report_date)
    lines = read_lines(pdf_path)
    full_text = "\n".join(l.text for l in lines)
    warnings: list[str] = []

    printed, year_in_pdf = None, None
    if m := DATE_RE.search(full_text):
        printed = m.group(0)
        if (int(m.group(1)), int(m.group(2))) != (report_date.day, report_date.month):
            warnings.append(f"printed date {printed!r} != file date {report_date}")
    if m := YEAR_RE.search(full_text):
        year_in_pdf = int(m.group(1))
        if year_in_pdf != report_date.year:
            warnings.append(f"year in PDF {year_in_pdf} != file year {report_date.year}")

    has_dengue_title = any(l.section == "dengue" for l in lines)
    if not has_dengue_title:
        warnings.append("no 'Daily Report of Dengue' title found; using all lines")
    dengue_lines = [l for l in lines if l.section == "dengue"] if has_dengue_title else lines
    mentions_bbmp = "bbmp" in full_text.lower()

    anchors = column_anchors(lines)
    rows: list[AreaRow] = []
    seen: set[str] = set()
    unparsed = 0
    for i, line in enumerate(dengue_lines):
        if len(line.numbers) < (8 if line.page in anchors and line.label else 10):
            if line.numbers and line.label and len(line.numbers) >= 4:
                unparsed += 1
            continue
        label = line.label
        inferred = False
        if label and "total" in label.lower():
            area = "STATE_TOTAL"
        elif label:
            area = canonical_area(label)
        else:
            # Unlabelled row: infer from shape. BBMP has no "blocks" column and zero "affected" counts.
            n = len(line.numbers)
            if n in (10, 16) and line.numbers[:4] == [0, 0, 0, 0] and mentions_bbmp:
                area, inferred = "BBMP", True
            elif n in (11, 17) and line.numbers[0] >= 100:
                area, inferred = "STATE_TOTAL", True
            else:
                unparsed += 1
                continue

        parsed, w = (None, [])
        if line.page in anchors:
            parsed, w = interpret_by_position(line, anchors[line.page])
        if parsed is None:
            parsed, w = interpret_numbers(line.numbers)
        if parsed is None:
            unparsed += 1
            continue
        if parsed["cumulative"] is None and i + 1 < len(dengue_lines) and _is_cumulative_continuation(dengue_lines[i + 1]):
            parsed["cumulative"] = Counts.from_list(dengue_lines[i + 1].numbers)
            w.append("cumulative taken from following line")
        if area in seen:
            warnings.append(f"duplicate row for {area} ignored: {line.text[:60]!r}")
            continue
        seen.add(area)
        if inferred:
            w.append("label inferred from row shape")
        warnings.extend(f"{area}: {msg}" for msg in w)
        rows.append(AreaRow(area=area, raw_label=label or None, inferred_label=inferred, **parsed))

    if unparsed:
        warnings.append(f"{unparsed} numeric line(s) could not be interpreted")
    if not any(r.area == "BBMP" for r in rows):
        warnings.append("BBMP row not found")

    return Bulletin(report_date=report_date, printed_date=printed, year_in_pdf=year_in_pdf,
                    extractor="rule", rows=rows, warnings=warnings, source_file=str(pdf_path))
