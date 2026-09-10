from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON, desc, func
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import CommonMixin, TenantMixin, get_utc_now

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
    call_logs = relationship("CallLog", back_populates="company")
    appointments = relationship("Appointment", back_populates="company", cascade="all, delete-orphan")

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
    appointments = relationship("Appointment", back_populates="contact")

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
    notes = Column(Text, nullable=True)
    last_call_at = Column(DateTime(timezone=True), nullable=True)
    last_call_notes = Column(Text, nullable=True)
    last_call_outcome = Column(String(100), nullable=True)

    # Relationships
    organization = relationship("Organization", back_populates="leads")
    company = relationship("Company", back_populates="leads")
    contact = relationship("Contact", back_populates="leads")
    conversations = relationship("Conversation", back_populates="lead", cascade="all, delete-orphan")
    opportunities = relationship("Opportunity", back_populates="lead", cascade="all, delete-orphan")
    call_logs = relationship("CallLog", back_populates="lead", cascade="all, delete-orphan", order_by=lambda: desc(CallLog.called_at))
    appointments = relationship("Appointment", back_populates="lead", cascade="all, delete-orphan", order_by=lambda: desc(Appointment.scheduled_at))

class CallLog(Base, CommonMixin, TenantMixin):
    __tablename__ = "call_logs"

    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    caller_name = Column(String(100), nullable=True)
    called_at = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, default=0, nullable=True)
    outcome = Column(String(100), default="connected", nullable=False)  # connected, left_voicemail, gatekeeper, busy, wrong_number, interested, scheduled_demo
    notes = Column(Text, nullable=False)  # What was said / discussion notes
    next_steps = Column(Text, nullable=True)

    # Relationships
    lead = relationship("Lead", back_populates="call_logs")
    company = relationship("Company", back_populates="call_logs")
    contact = relationship("Contact")

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

class ClientAccount(Base, CommonMixin, TenantMixin):
    __tablename__ = "client_accounts"

    company_id = Column(String(36), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    primary_contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)
    account_name = Column(String(255), nullable=False, index=True)
    account_tier = Column(String(50), default="standard", nullable=False)  # standard, premium, enterprise, vip
    status = Column(String(50), default="active", nullable=False)  # active, at_risk, churned, paused
    total_revenue = Column(Float, default=0.0, nullable=False)
    order_count = Column(Integer, default=0, nullable=False)
    contract_start_date = Column(DateTime(timezone=True), nullable=True)
    renewal_date = Column(DateTime(timezone=True), nullable=True)
    reorder_cadence_days = Column(Integer, default=30, nullable=False)
    next_reorder_date = Column(DateTime(timezone=True), nullable=True)
    account_manager = Column(String(100), default="Primary Sales Manager", nullable=False)
    notes = Column(Text, nullable=True)

    # Card on File & Recurring Subscriptions
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    has_payment_method_on_file = Column(Boolean, default=False, nullable=False)
    card_brand = Column(String(50), nullable=True)
    card_last4 = Column(String(10), nullable=True)
    auto_charge_enabled = Column(Boolean, default=False, nullable=False)
    auto_charge_limit = Column(Float, nullable=True)
    payment_method_type = Column(String(50), default="card", nullable=False)

    # Customer Self-Service Portal Access Token
    portal_access_token = Column(String(100), unique=True, index=True, nullable=True)
    portal_token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    company = relationship("Company")
    primary_contact = relationship("Contact")
    sales = relationship("ClientSale", back_populates="client", cascade="all, delete-orphan", order_by=lambda: desc(ClientSale.sale_date))

class ClientSale(Base, CommonMixin, TenantMixin):
    __tablename__ = "client_sales"

    client_id = Column(String(36), ForeignKey("client_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    order_number = Column(String(100), nullable=False, index=True)
    amount = Column(Float, default=0.0, nullable=False)
    sale_date = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(50), default="completed", nullable=False)  # completed, pending, invoiced, delivered, cancelled
    payment_method = Column(String(50), default="credit_terms_30", nullable=False)  # credit_terms_30, credit_card, ach_wire, check
    payment_status = Column(String(50), default="unpaid", nullable=False, index=True)  # unpaid, paid, refunded
    stripe_session_id = Column(String(255), nullable=True, index=True)
    stripe_payment_intent_id = Column(String(255), nullable=True)
    stripe_checkout_url = Column(String(500), nullable=True)
    auto_fulfill_on_payment = Column(Boolean, default=True, nullable=False)
    customer_email = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    items_summary = Column(Text, nullable=False)
    sales_rep_name = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    client = relationship("ClientAccount", back_populates="sales")
    lead = relationship("Lead")
    purchase_orders = relationship("PurchaseOrder", back_populates="client_sale", cascade="all, delete-orphan", order_by="desc(PurchaseOrder.created_at)")
    notifications = relationship("CustomerNotification", back_populates="client_sale", cascade="all, delete-orphan", order_by="desc(CustomerNotification.sent_at)")

class CustomerNotification(Base, CommonMixin, TenantMixin):
    __tablename__ = "customer_notifications"

    client_sale_id = Column(String(36), ForeignKey("client_sales.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient = Column(String(255), nullable=False)
    channel = Column(String(50), default="email", nullable=False)  # email, sms
    event_type = Column(String(50), nullable=False)  # order_confirmed, payment_received, dispatched, in_transit, out_for_delivery, delivered
    title = Column(String(255), nullable=False)
    message_body = Column(Text, nullable=False)
    tracking_url = Column(String(500), nullable=True)
    sent_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    status = Column(String(50), default="sent", nullable=False)  # sent, simulated, failed

    # Relationships
    client_sale = relationship("ClientSale", back_populates="notifications")

class Appointment(Base, CommonMixin, TenantMixin):
    __tablename__ = "appointments"

    lead_id = Column(String(36), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(String(36), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    contact_id = Column(String(36), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True)

    title = Column(String(255), nullable=False, default="Executive Procurement Consultation")
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_minutes = Column(Integer, default=30, nullable=False)
    status = Column(String(50), default="scheduled", nullable=False, index=True)  # scheduled, completed, cancelled, no_show, rescheduled
    meeting_url = Column(String(255), nullable=True)

    closer_name = Column(String(100), default="Senior Sales Executive", nullable=False)
    closer_email = Column(String(255), nullable=True)
    executive_briefing = Column(JSON, default=dict, nullable=False)
    notes = Column(Text, nullable=True)
    booked_by_agent = Column(Boolean, default=True, nullable=False)

    # Relationships
    lead = relationship("Lead", back_populates="appointments")
    company = relationship("Company", back_populates="appointments")
    contact = relationship("Contact", back_populates="appointments")

