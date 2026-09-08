import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import declarative_mixin, declared_attr
from app.core.database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)

@declarative_mixin
class CommonMixin:
    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False)

@declarative_mixin
class TenantMixin:
    @declared_attr
    def organization_id(cls):
        return Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
