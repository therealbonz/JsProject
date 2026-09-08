from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import CommonMixin, TenantMixin

class Company(Base, CommonMixin, TenantMixin):
    __tablename__ = "companies"

    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), nullable=True, index=True)
    industry = Column(String(100), nullable=True)
    employee_range = Column(String(50), nullable=True)
    phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    research_data = Column(JSON, default=dict, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="companies")
    contacts = relationship("Contact", back_populates="company", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="company", cascade="all, delete-orphan")

class Contact(Base, CommonMixin, TenantMixin):
    __tablename__ = "contacts"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(50), nullable=True)
    job_title = Column(String(100), nullable=True)
    decision_maker_role = Column(String(50), default="other", nullable=False)  # purchasing, facility_mgr, operations, owner, gatekeeper, other
    is_primary = Column(Boolean, default=False, nullable=False)

    # Relationships
    company = relationship("Company", back_populates="contacts")
    leads = relationship("Lead", back_populates="contact")

class Lead(Base, CommonMixin, TenantMixin):
    __tablename__ = "leads"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)

    lead_score = Column(Integer, default=50, nullable=False)  # 0 to 100
    pipeline_stage = Column(String(50), default="new", nullable=False, index=True)  
    # new, researching, ready_contact, contacted, connected, qualified, proposal, negotiation, won, lost
    status = Column(String(50), default="active", nullable=False)  # active, paused, dnc, converted

    assigned_agent_id = Column(String(100), default="sales_agent_primary", nullable=False)
    last_contacted_at = Column(DateTime(timezone=True), nullable=True)
    next_action_at = Column(DateTime(timezone=True), nullable=True)
    next_action_type = Column(String(100), nullable=True)
    research_summary = Column(Text, nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="leads")
    company = relationship("Company", back_populates="leads")
    contact = relationship("Contact", back_populates="leads")
    conversations = relationship("Conversation", back_populates="lead", cascade="all, delete-orphan")
    opportunities = relationship("Opportunity", back_populates="lead", cascade="all, delete-orphan")

class Opportunity(Base, CommonMixin, TenantMixin):
    __tablename__ = "opportunities"

    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    estimated_value = Column(Float, default=0.0, nullable=False)
    probability = Column(Float, default=0.2, nullable=False)  # 0.0 to 1.0
    stage = Column(String(50), default="discovery", nullable=False)
    expected_close_date = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    lead = relationship("Lead", back_populates="opportunities")

class Product(Base, CommonMixin, TenantMixin):
    __tablename__ = "products"

    name = Column(String(255), nullable=False, index=True)
    sku = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    unit_price = Column(Float, default=0.0, nullable=False)
    min_allowed_price = Column(Float, default=0.0, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="products")

class KnowledgeDocument(Base, CommonMixin, TenantMixin):
    __tablename__ = "knowledge_documents"

    title = Column(String(255), nullable=False)
    category = Column(String(50), default="faq", nullable=False)  # faq, pricing, script, policy, product_sheet
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="knowledge_docs")
