from sqlalchemy import Column, String, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import CommonMixin, TenantMixin, get_utc_now

class CustomDomain(Base, CommonMixin, TenantMixin):
    __tablename__ = "custom_domains"

    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    domain = Column(String(255), unique=True, nullable=False, index=True)
    cname_target = Column(String(255), default="therealbonz.com", nullable=False)
    verification_token = Column(String(100), nullable=False, index=True)
    verification_method = Column(String(50), default="cname", nullable=False)  # cname, txt
    verification_status = Column(String(50), default="pending", nullable=False, index=True)  # pending, verified, failed
    verified_at = Column(DateTime(timezone=True), nullable=True)

    is_primary = Column(Boolean, default=False, nullable=False)
    ssl_status = Column(String(50), default="pending", nullable=False)  # pending, active, failed
    ssl_provisioned_at = Column(DateTime(timezone=True), nullable=True)

    dns_check_payload = Column(JSON, default=dict, nullable=False)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Optional domain-specific white-label overrides (e.g. brand name, logo, accent color, footer)
    custom_theme_overrides = Column(JSON, default=dict, nullable=False)

    # Relationships
    organization = relationship("Organization", back_populates="custom_domains")
