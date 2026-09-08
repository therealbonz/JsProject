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

class ExtractedDecisionMaker(BaseModel):
    first_name: str
    last_name: str
    job_title: str
    email: Optional[str] = None
    phone: Optional[str] = None
    decision_maker_role: str = "purchasing"  # owner, c_level, purchasing, operations, facility_mgr, gatekeeper, other
    confidence_score: float = 0.85
    notes: Optional[str] = None

class BusinessIntelligenceResult(BaseModel):
    company_name: str
    company_overview: str
    estimated_employee_count: Optional[str] = None
    ownership_structure: str  # e.g., "Privately owned by Founder & CEO John Doe"
    key_decision_makers: List[ExtractedDecisionMaker] = []
    pain_points: List[str] = []
    procurement_signals: List[str] = []
    suggested_angle: str
    confidence_score: float = 0.88

class AppointmentBookingRequest(BaseModel):
    scheduled_at: Optional[str] = None  # ISO format string or None for next business day default
    duration_minutes: Optional[int] = 30
    closer_name: Optional[str] = "Senior Sales Executive"
    closer_email: Optional[str] = None
    meeting_url: Optional[str] = None
    notes: Optional[str] = None

class CloserBriefingDossier(BaseModel):
    company_summary: str
    target_prospect: Dict[str, Any]
    key_pain_points: List[str]
    discussion_highlights: List[str]
    objections_handled: List[str]
    recommended_closing_strategy: str
    target_products: List[str]
    estimated_deal_potential: Optional[str] = None

class AppointmentBookingResult(BaseModel):
    appointment_id: str
    lead_id: str
    company_name: str
    contact_name: str
    scheduled_at: str
    duration_minutes: int
    closer_name: str
    closer_email: Optional[str] = None
    meeting_url: str
    executive_briefing: Dict[str, Any]
    status: str

class InboundReplyAnalysis(BaseModel):
    intent: str  # interested, inquiry, objection, out_of_office, not_interested, gatekeeper_referral, unsubscribe, appointment_request
    sentiment: str  # positive, neutral, hesitant, hostile
    summary: str
    requires_hitl: bool
    hitl_reason: Optional[str] = None
    suggested_reply: Optional[str] = None
    confidence_score: float
    detected_discount_request: Optional[float] = None
    referred_contact: Optional[ExtractedDecisionMaker] = None
    appointment_requested: Optional[bool] = False
    proposed_meeting_time: Optional[str] = None

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
