from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

class HARActionRequest(BaseModel):
    action: str  # approve, reject, take_over, override_reply
    instructions: Optional[str] = None
    custom_reply: Optional[str] = None

class HARResponse(BaseModel):
    id: str
    organization_id: str
    conversation_id: str
    lead_id: str
    trigger_reason: str
    situation_summary: str
    suggested_options: List[str]
    ai_recommendation: Optional[str]
    confidence_score: float
    status: str
    reviewed_by_user_id: Optional[str]
    reviewer_instructions: Optional[str]
    created_at: datetime
    resolved_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)

class AuditLogResponse(BaseModel):
    id: str
    organization_id: str
    actor_type: str
    actor_id: Optional[str]
    action: str
    target_entity: Optional[str]
    target_id: Optional[str]
    payload: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
