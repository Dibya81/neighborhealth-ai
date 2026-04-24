from __future__ import annotations
from pydantic import BaseModel, field_validator
from typing import Optional, List
from uuid import UUID

class SubscriptionCreate(BaseModel):
    ward_id: str
    contact: str
    contact_type: str
    threshold: Optional[int] = 70
    user_id: Optional[UUID] = None
    name: Optional[str] = None
    email: Optional[str] = None
    notify_diseases: Optional[list[str]] = ["dengue"]

    @field_validator("contact_type")
    @classmethod
    def validate_type(cls, v):
        if v not in ("sms", "email"):
            raise ValueError("contact_type must be 'sms' or 'email'")
        return v

    @field_validator("threshold")
    @classmethod
    def validate_threshold(cls, v):
        if v is not None and not (1 <= v <= 100):
            raise ValueError("threshold must be between 1 and 100")
        return v

class SubscriptionResponse(BaseModel):
    id: str
    ward_id: str
    contact: str
    contact_type: str
    threshold: int
    user_id: Optional[UUID]
    name: Optional[str]
    email: Optional[str]
    notify_diseases: list[str]
    active: bool

class CancelResponse(BaseModel):
    id: str
    status: str
