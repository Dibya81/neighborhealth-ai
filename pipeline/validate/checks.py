"""Validation rules.

Row-level checks run on a single bulletin. Series-level checks run across bulletins over time.
Each failed check returns a short code, so the evaluation can measure how well the validator
catches real extraction errors (i.e. how much we can trust a row that passes).
"""
from __future__ import annotations

from pipeline.extract.schema import AreaRow, Bulletin, Counts


def check_counts(c: Counts | None, prefix: str) -> list[str]:
    if c is None:
        return []
    flags = []
    if None not in (c.igm, c.ns1, c.total_pos) and c.igm + c.ns1 != c.total_pos:
        flags.append(f"{prefix}_sum_mismatch")       # IgM + NS1 != Total
    if None not in (c.total_pos, c.samples) and c.samples > 0 and c.total_pos > c.samples:
        flags.append(f"{prefix}_pos_gt_samples")
    if c.total_pos is not None and c.total_pos < 0:
        flags.append(f"{prefix}_negative")
    return flags


def check_row(row: AreaRow) -> list[str]:
    flags = check_counts(row.on_day, "day") + check_counts(row.cumulative, "cum")
    if row.cumulative is None:
        flags.append("cum_missing")
    elif None not in (row.on_day.total_pos, row.cumulative.total_pos) and row.on_day.total_pos > row.cumulative.total_pos:
        flags.append("day_gt_cum")
    if row.inferred_label:
        flags.append("label_inferred")              # informational, not an error by itself
    return flags


def check_bulletin(b: Bulletin) -> dict[str, list[str]]:
    """Flags per area, plus a '_bulletin' entry for whole-document checks."""
    out = {r.area: check_row(r) for r in b.rows}
    doc_flags = []
    total = b.get("STATE_TOTAL")
    districts = [r for r in b.rows if r.area not in ("STATE_TOTAL", "BBMP")]
    if total and total.cumulative and total.cumulative.total_pos is not None and districts:
        s = sum((r.cumulative.total_pos or 0) for r in districts if r.cumulative)
        bbmp = b.get("BBMP")
        s_with_bbmp = s + ((bbmp.cumulative.total_pos or 0) if bbmp and bbmp.cumulative else 0)
        if total.cumulative.total_pos not in (s, s_with_bbmp):
            doc_flags.append("state_total_mismatch")
    if "BBMP" not in out:
        doc_flags.append("bbmp_missing")
    if any("date" in w for w in b.warnings):
        doc_flags.append("date_mismatch")
    out["_bulletin"] = doc_flags
    return out


HARD_FLAGS = {"day_sum_mismatch", "cum_sum_mismatch", "day_pos_gt_samples", "cum_pos_gt_samples",
              "day_negative", "cum_negative", "day_gt_cum"}


def is_trustworthy(flags: list[str]) -> bool:
    return not any(f in HARD_FLAGS for f in flags)
