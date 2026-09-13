from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

class CopilotChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Customer message to the AI support copilot")
    conversation_id: Optional[str] = Field(None, description="Optional existing conversation ID to continue thread")

class CopilotChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: str
    reply: str
    sender_type: str = "ai_agent"
    sentiment: str = "neutral"
    is_escalated: bool = False
    escalation_reason: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_score: float = 0.95
    created_at: Optional[datetime] = None

class CopilotMessageDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    sender_type: str  # ai_agent, human_rep, customer
    sender_name: Optional[str] = None
    direction: str = "outbound"
    body_text: str
    ai_confidence: Optional[float] = None
    ai_reasoning: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None

class CopilotConversationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: Optional[str] = None
    client_name: Optional[str] = None
    company_name: Optional[str] = None
    channel: str = "customer_portal"
    status: str = "active"  # active, waiting_on_human, closed, resolved
    sentiment: str = "neutral"  # positive, neutral, hesitant, hostile, frustrated
    current_objective: Optional[str] = None
    message_count: int = 0
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    is_escalated: bool = False
    hitl_request_id: Optional[str] = None
    account_manager: Optional[str] = None

class CopilotConversationDetail(BaseModel):
    conversation: CopilotConversationSummary
    messages: List[CopilotMessageDTO]
    client_account_summary: Optional[Dict[str, Any]] = None

class CopilotHumanReplyRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Human sales rep takeover reply text")
    resolve_ticket: Optional[bool] = Field(False, description="Set True to mark the conversation resolved")

class CopilotEscalateRequest(BaseModel):
    reason: Optional[str] = Field("Customer explicitly requested human assistance", description="Reason for escalation")
