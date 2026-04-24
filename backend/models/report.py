from pydantic import BaseModel, field_validator
from typing import Optional

class ReportCreate(BaseModel):
    ward_id: str
    lat: float
    lng: float
    description: Optional[str] = None
    photo_url: Optional[str] = None

    @field_validator("lat")
    @classmethod
    def validate_lat(cls, v):
        if not (12.7 <= v <= 13.2):
            raise ValueError("Latitude must be within Bengaluru bounds (12.7–13.2)")
        return v

    @field_validator("lng")
    @classmethod
    def validate_lng(cls, v):
        if not (77.3 <= v <= 77.9):
            raise ValueError("Longitude must be within Bengaluru bounds (77.3–77.9)")
        return v

class ReportResponse(BaseModel):
    id: str
    status: str
    message: str

class ReportItem(BaseModel):
    id: str
    lat: float
    lng: float
    description: Optional[str] = None
    photo_url: Optional[str] = None
    status: str
    reported_at: str
