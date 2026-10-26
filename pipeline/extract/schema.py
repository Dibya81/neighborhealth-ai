"""Typed schema for one extracted bulletin. Both extractors (rule-based and LLM) produce this."""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

COUNT_FIELDS = ["suspected", "samples", "igm", "ns1", "total_pos", "deaths"]


class Counts(BaseModel):
    suspected: Optional[int] = None   # suspected cases
    samples: Optional[int] = None     # blood samples tested
    igm: Optional[int] = None         # IgM MAC ELISA positives
    ns1: Optional[int] = None         # NS1 antigen (or "Others") positives
    total_pos: Optional[int] = None   # total positives  <- the main signal
    deaths: Optional[int] = None

    @classmethod
    def from_list(cls, values: list[int]) -> "Counts":
        return cls(**dict(zip(COUNT_FIELDS, values)))


class AreaRow(BaseModel):
    area: str                          # canonical name: "BBMP", "Bengaluru Urban", ..., "STATE_TOTAL"
    raw_label: Optional[str] = None
    inferred_label: bool = False       # True when the label was missing in the PDF and we inferred it
    blocks: Optional[int] = None
    taluks_affected: Optional[int] = None
    phc_affected: Optional[int] = None
    villages_affected: Optional[int] = None
    population_affected: Optional[int] = None
    on_day: Counts = Field(default_factory=Counts)
    cumulative: Optional[Counts] = None


class Bulletin(BaseModel):
    report_date: date                  # from the file name (authoritative); cross-checked with the PDF text
    printed_date: Optional[str] = None
    year_in_pdf: Optional[int] = None
    disease: str = "dengue"
    extractor: str                     # "rule" | "llm" | "reconciled"
    rows: list[AreaRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    source_file: Optional[str] = None

    def get(self, area: str) -> Optional[AreaRow]:
        return next((r for r in self.rows if r.area == area), None)
