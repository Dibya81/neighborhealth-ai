"""Pick one value per (date, area) from the rule-based and LLM extractions, with provenance.

Decision rule (kept deliberately simple and explainable):
  1. Drop candidates that fail hard validation checks.
  2. If both survive and agree on cumulative positives -> use it (agree=True).
  3. If both survive and disagree -> use the extractor that scored better in the evaluation
     (`prefer`, default "rule"), and flag the row so it can be reviewed.
  4. If only one survives -> use it. If none -> keep the rule row but mark trusted=False.
"""
from __future__ import annotations

import pandas as pd

from pipeline.extract.schema import COUNT_FIELDS, AreaRow, Bulletin
from pipeline.validate.checks import check_bulletin, is_trustworthy


def _flatten(row: AreaRow) -> dict:
    d = {f"day_{k}": getattr(row.on_day, k) for k in COUNT_FIELDS}
    d.update({f"cum_{k}": (getattr(row.cumulative, k) if row.cumulative else None) for k in COUNT_FIELDS})
    return d


def reconcile(extractions: dict[str, dict[str, Bulletin]], keep_areas: list[str],
              prefer: str = "rule") -> pd.DataFrame:
    """extractions: {iso_date: {"rule": Bulletin, "llm": Bulletin (optional)}}"""
    records = []
    for iso, by_ext in sorted(extractions.items()):
        flags_by_ext = {name: check_bulletin(b) for name, b in by_ext.items()}
        for area in keep_areas:
            cands = []
            for name, b in by_ext.items():
                row = b.get(area)
                if row is None:
                    continue
                flags = flags_by_ext[name].get(area, [])
                cands.append((name, row, flags, is_trustworthy(flags)))
            if not cands:
                records.append({"date": iso, "area": area, "extractor": None, "trusted": False,
                                "agree": None, "flags": "not_found"})
                continue
            good = [c for c in cands if c[3]]
            agree = None
            if len(good) >= 2:
                vals = {c[1].cumulative.total_pos if c[1].cumulative else None for c in good}
                agree = len(vals) == 1
                chosen = next((c for c in good if c[0] == prefer), good[0])
            elif len(good) == 1:
                chosen = good[0]
            else:
                chosen = next((c for c in cands if c[0] == prefer), cands[0])
            name, row, flags, trusted = chosen
            extra = [] if agree in (None, True) else ["extractors_disagree"]
            records.append({"date": iso, "area": area, "extractor": name, "trusted": trusted, "agree": agree,
                            "flags": ";".join(flags + extra), "inferred_label": row.inferred_label,
                            # Year the cumulative counts refer to (early-January files still report the old year)
                            "cum_year": b.year_in_pdf or int(iso[:4]), **_flatten(row)})
    df = pd.DataFrame.from_records(records)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df
