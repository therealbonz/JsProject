from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class CampaignDialRequest(BaseModel):
    batch_size: int = Field(default=10, ge=1, le=100)
    delay_seconds: float = Field(default=0.5, ge=0.0, le=10.0)
    voice_persona: str = "Amber (Polly.Danielle)"
    simulate: bool = True
    simulated_outcome: Optional[str] = None  # None (random realistic), "booked", "voicemail", "dnc", "connected"

class CampaignDialResult(BaseModel):
    lead_id: str
    contact_name: str
    phone: str
    trade_service: str
    outcome: str
    duration_seconds: int
    transcript: str
    appointment_id: Optional[str] = None
    appointment_slot: Optional[str] = None
    call_sid: str
    sms_followup_sent: bool = False

class CampaignBatchProgress(BaseModel):
    campaign_id: str
    campaign_name: str
    trade_service: str
    status: str
    total_leads: int
    pending_leads: int
    dialed_count: int
    connected_count: int
    booked_count: int
    voicemail_count: int
    dnc_count: int
    results: List[CampaignDialResult] = Field(default_factory=list)
