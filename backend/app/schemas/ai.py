from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

class LeadResearchResult(BaseModel):
    lead_score: int
    company_overview: str
    decision_maker_analysis: str
    suggested_angle: str
    pain_points: List[str]
    confidence_score: float

class OutreachDraftResult(BaseModel):
    subject: str
    body_text: str
    value_proposition: str
    call_to_action: str
    confidence_score: float

class InboundReplyAnalysis(BaseModel):
    intent: str  # interested, inquiry, objection, out_of_office, not_interested, gatekeeper_referral, unsubscribe
    sentiment: str  # positive, neutral, hesitant, hostile
    summary: str
    requires_hitl: bool
    hitl_reason: Optional[str] = None
    suggested_reply: Optional[str] = None
    confidence_score: float
    detected_discount_request: Optional[float] = None

class MessageSendRequest(BaseModel):
    conversation_id: str
    subject: Optional[str] = None
    body_text: str

class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    sender_type: str
    sender_name: Optional[str]
    direction: str
    subject: Optional[str]
    body_text: str
    ai_reasoning: Dict[str, Any]
    ai_confidence: Optional[float]

    model_config = ConfigDict(from_attributes=True)
