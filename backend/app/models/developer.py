from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey, JSON, desc
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import CommonMixin, TenantMixin, get_utc_now

class ApiKey(Base, CommonMixin, TenantMixin):
    __tablename__ = "api_keys"

    key_name = Column(String(255), nullable=False)
    key_prefix = Column(String(20), nullable=False, index=True)  # e.g., "jsp_live_a1b2c3d4"
    hashed_key = Column(String(64), nullable=False, index=True)  # SHA-256 hex digest
    scopes = Column(JSON, default=lambda: ["*"], nullable=False)  # ["*"] or ["orders:read", ...]
    rate_limit_per_minute = Column(Integer, default=120, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    created_by = relationship("User")


class WebhookSubscription(Base, CommonMixin, TenantMixin):
    __tablename__ = "webhook_subscriptions"

    target_url = Column(String(500), nullable=False)
    description = Column(String(255), nullable=True)
    events = Column(JSON, default=list, nullable=False)  # e.g., ["order.created", "payment.succeeded"]
    secret_key = Column(String(64), nullable=False)  # e.g., "whsec_..."
    is_active = Column(Boolean, default=True, nullable=False)
    failure_count = Column(Integer, default=0, nullable=False)

    # Relationships
    deliveries = relationship(
        "WebhookDeliveryLog",
        back_populates="subscription",
        cascade="all, delete-orphan",
        order_by=lambda: desc(WebhookDeliveryLog.delivered_at)
    )


class WebhookDeliveryLog(Base, CommonMixin, TenantMixin):
    __tablename__ = "webhook_delivery_logs"

    subscription_id = Column(String(36), ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)
    delivery_uuid = Column(String(36), nullable=False, index=True)
    payload_json = Column(JSON, default=dict, nullable=False)
    response_status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="delivered", nullable=False)  # delivered, failed, simulated
    delivered_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)

    # Relationships
    subscription = relationship("WebhookSubscription", back_populates="deliveries")
