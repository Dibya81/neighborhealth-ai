from __future__ import annotations
from pydantic import BaseModel
from typing import Optional

class WardBase(BaseModel):
    id: str
    name: str
    constituency: Optional[str] = None
    population_density: Optional[float] = None

class WardListResponse(BaseModel):
    wards: list[WardBase]
    total: int
