from sqlalchemy import Column, String, Boolean, Float, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import CommonMixin, TenantMixin

class Organization(Base, CommonMixin):
    __tablename__ = "organizations"

    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(50), default="active", nullable=False)

    # White-Label Branding & Theme
    brand_name = Column(String(255), nullable=True)
    brand_logo_url = Column(String(500), nullable=True)
    brand_accent_color = Column(String(50), default="#4f46e5", nullable=True)
    support_email = Column(String(255), nullable=True)
    support_phone = Column(String(100), nullable=True)
    custom_footer_text = Column(String(500), nullable=True)
    tracking_portal_notice = Column(Text, nullable=True)

    # Merchant Payment Gateways (Stripe Connect / Custom Keys)
    stripe_publishable_key = Column(String(255), nullable=True)
    stripe_secret_key = Column(String(255), nullable=True)
    stripe_webhook_secret = Column(String(255), nullable=True)

    # Live Multi-Channel Notification Gateways (Twilio SMS & SendGrid/Postmark Email)
    twilio_account_sid = Column(String(100), nullable=True)
    twilio_auth_token = Column(String(100), nullable=True)
    twilio_from_number = Column(String(50), nullable=True)
    sendgrid_api_key = Column(String(100), nullable=True)
    email_from_address = Column(String(255), nullable=True)
    email_from_name = Column(String(255), nullable=True)
    default_commission_rate = Column(Float, default=10.0, nullable=False)

    # Relationships
    memberships = relationship("OrganizationMembership", back_populates="organization", cascade="all, delete-orphan")
    ai_config = relationship("AIConfiguration", back_populates="organization", uselist=False, cascade="all, delete-orphan")
    companies = relationship("Company", back_populates="organization", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="organization", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="organization", cascade="all, delete-orphan")
    knowledge_docs = relationship("KnowledgeDocument", back_populates="organization", cascade="all, delete-orphan")

class User(Base, CommonMixin):
    __tablename__ = "users"

    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    # Relationships
    memberships = relationship("OrganizationMembership", back_populates="user", cascade="all, delete-orphan")

class OrganizationMembership(Base, CommonMixin, TenantMixin):
    __tablename__ = "organization_memberships"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default="sales_rep", nullable=False)  # super_admin, admin, sales_manager, sales_rep, viewer
    commission_rate_pct = Column(Float, default=10.0, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="memberships")
    user = relationship("User", back_populates="memberships")

class AIConfiguration(Base, CommonMixin, TenantMixin):
    __tablename__ = "ai_configurations"

    company_name = Column(String(255), nullable=True)
    company_description = Column(Text, nullable=True)
    autonomy_level = Column(String(50), default="semi_autonomous", nullable=False)  # assistant, semi_autonomous, autonomous
    max_discount_pct = Column(Float, default=10.0, nullable=False)
    tone_of_voice = Column(String(100), default="professional, helpful, consultative", nullable=False)
    prohibited_phrases = Column(JSON, default=list, nullable=False)
    sales_guidelines = Column(Text, nullable=True)
    hitl_required_for_closing = Column(Boolean, default=True, nullable=False)
    business_hours = Column(JSON, default=dict, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="ai_config")
