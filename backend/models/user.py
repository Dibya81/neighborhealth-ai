from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime

class SavedLocation(BaseModel):
    label: str          # "home", "office", "school"
    ward_id: str
    lat: Optional[float] = None
    lng: Optional[float] = None

class UserBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    home_ward_id: Optional[str] = None
    health_conditions: Optional[List[str]] = []
    saved_locations: Optional[List[SavedLocation]] = []

class UserCreate(UserBase):
    pass

class UserResponse(UserBase):
    id: UUID
    created_at: datetime
    saved_locations: Optional[Any] = [] # Handle as JSONB

    class Config:
        from_attributes = True
