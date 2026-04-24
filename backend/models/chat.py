from pydantic import BaseModel
from typing import Optional, List

class ChatRequest(BaseModel):
    ward_id: str
    message: str
    language: Optional[str] = "en"
    simulation_mode: Optional[str] = None
    user_health_conditions: Optional[List[str]] = None
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    ward_id: str
    ward_context_used: bool
    language: str
