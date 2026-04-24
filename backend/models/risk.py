from __future__ import annotations
from pydantic import BaseModel
from typing import Optional
from datetime import date

class RiskSignals(BaseModel):
    rainfall_7d: Optional[float] = None
    temp_avg: Optional[float] = None
    humidity_avg: Optional[float] = None
    dengue_cases: Optional[int] = None
    report_count: Optional[int] = None

class RiskScoreSummary(BaseModel):
    ward_id: str
    risk_score: float
    risk_level: str
    disease: str
    score_date: Optional[str] = None

class RiskScoreDetail(BaseModel):
    ward_id: str
    ward_name: Optional[str] = None
    risk_score: float
    risk_level: str
    disease: str
    score_date: Optional[str] = None
    signals: Optional[RiskSignals] = None
    reasons: Optional[list[str]] = None
    trend: Optional[list[float]] = None
    trend_direction: Optional[str] = None
    model_version: Optional[str] = None

class RiskAllResponse(BaseModel):
    generated_at: str
    total_wards: int
    wards: list[RiskScoreSummary]

class RiskHistoryEntry(BaseModel):
    date: str
    risk_score: float
    risk_level: str

class RiskHistoryResponse(BaseModel):
    ward_id: str
    history: list[RiskHistoryEntry]
