from sqlalchemy import Column, String, Text, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import CommonMixin, TenantMixin

class Conversation(Base, CommonMixin, TenantMixin):
    __tablename__ = "conversations"

    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    channel = Column(String(50), default="email", nullable=False)  # email, phone, web_chat
    status = Column(String(50), default="active", nullable=False)  # active, waiting_on_lead, waiting_on_human, closed
    ai_summary = Column(Text, nullable=True)
    sentiment = Column(String(50), default="neutral", nullable=False)  # positive, neutral, hesitant, hostile
    current_objective = Column(String(255), nullable=True)

    # Relationships
    lead = relationship("Lead", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    assistance_requests = relationship("HumanAssistanceRequest", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base, CommonMixin):
    __tablename__ = "messages"

    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_type = Column(String(50), nullable=False)  # ai_agent, human_rep, lead
    sender_name = Column(String(100), nullable=True)
    direction = Column(String(20), nullable=False)  # inbound, outbound
    subject = Column(String(255), nullable=True)
    body_text = Column(Text, nullable=False)
    email_message_id = Column(String(255), nullable=True, index=True)
    email_in_reply_to = Column(String(255), nullable=True, index=True)
    ai_reasoning = Column(JSON, default=dict, nullable=False)
    ai_confidence = Column(Float, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
