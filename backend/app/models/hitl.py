from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import CommonMixin, TenantMixin

class HumanAssistanceRequest(Base, CommonMixin, TenantMixin):
    __tablename__ = "human_assistance_requests"

    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True)
    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)
    
    trigger_reason = Column(String(100), nullable=False)  # policy_discount, low_confidence, angry_lead, human_requested, complex_pricing
    situation_summary = Column(Text, nullable=False)
    suggested_options = Column(JSON, default=list, nullable=False)
    ai_recommendation = Column(Text, nullable=True)
    confidence_score = Column(Float, default=0.5, nullable=False)

    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, approved, rejected, taken_over, resolved
    reviewed_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewer_instructions = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="assistance_requests")

class AgentTask(Base, CommonMixin, TenantMixin):
    __tablename__ = "agent_tasks"

    task_type = Column(String(100), nullable=False, index=True)  # lead_research, draft_outreach, process_reply, scheduled_followup
    entity_type = Column(String(50), default="lead", nullable=False)  # lead, conversation, company
    entity_id = Column(String(36), nullable=False, index=True)
    status = Column(String(50), default="pending", nullable=False, index=True)  # pending, running, completed, failed, blocked_hitl
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    result_data = Column(JSON, default=dict, nullable=False)

class AuditLog(Base, CommonMixin, TenantMixin):
    __tablename__ = "audit_logs"

    actor_type = Column(String(50), nullable=False)  # ai_agent, human_rep, system
    actor_id = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False, index=True)  # email_sent, lead_scored, discount_requested, hitl_approved, conversation_takeover
    target_entity = Column(String(50), nullable=True)
    target_id = Column(String(36), nullable=True)
    payload = Column(JSON, default=dict, nullable=False)

class ComplianceDNC(Base, CommonMixin, TenantMixin):
    __tablename__ = "compliance_dnc"

    entity_type = Column(String(50), nullable=False)  # email, domain, phone
    value = Column(String(255), nullable=False, index=True)
    reason = Column(String(255), nullable=True)
