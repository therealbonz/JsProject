from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Boolean, Text, DateTime, ForeignKey, JSON, desc
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import CommonMixin, TenantMixin, get_utc_now

class MeteredUsageRecord(Base, CommonMixin, TenantMixin):
    __tablename__ = "metered_usage_records"

    client_id = Column(String(36), ForeignKey("client_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    license_id = Column(String(36), ForeignKey("saas_licenses.id", ondelete="CASCADE"), nullable=False, index=True)
    metric_name = Column(String(50), nullable=False, index=True)  # api_calls, ai_agent_runs, procurement_orders, edi_transactions, storage_mb
    quantity = Column(Float, default=1.0, nullable=False)
    idempotency_key = Column(String(100), nullable=True, index=True)
    source = Column(String(50), default="api_gateway", nullable=False)  # api_gateway, internal_agent, edi_pipeline, simulation
    billing_cycle_id = Column(String(36), ForeignKey("metered_billing_invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    recorded_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    metadata_json = Column(JSON, default=dict, nullable=False)

    # Relationships
    client = relationship("ClientAccount")
    license = relationship("SaaSLicense")
    invoice = relationship("MeteredBillingInvoice", back_populates="usage_records")


class MeteredBillingInvoice(Base, CommonMixin, TenantMixin):
    __tablename__ = "metered_billing_invoices"

    client_id = Column(String(36), ForeignKey("client_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    license_id = Column(String(36), ForeignKey("saas_licenses.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_number = Column(String(100), unique=True, nullable=False, index=True)
    cycle_start = Column(DateTime(timezone=True), nullable=False)
    cycle_end = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(50), default="settled", nullable=False, index=True)  # settled, pending, failed
    line_items = Column(JSON, default=list, nullable=False)
    # [
    #   {
    #     "metric_name": "api_calls",
    #     "display_name": "API Calls",
    #     "included_units": 100000,
    #     "consumed_units": 125000,
    #     "overage_units": 25000,
    #     "unit_overage_rate": 0.0015,
    #     "subtotal": 37.50
    #   }
    # ]
    subtotal_overage_amount = Column(Float, default=0.0, nullable=False)
    tax_amount = Column(Float, default=0.0, nullable=False)
    total_billed_amount = Column(Float, default=0.0, nullable=False)
    client_sale_id = Column(String(36), ForeignKey("client_sales.id", ondelete="SET NULL"), nullable=True, index=True)
    payment_method = Column(String(50), default="card_on_file", nullable=False)  # card_on_file, credit_terms, stripe_invoice
    payment_status = Column(String(50), default="paid", nullable=False)  # paid, unpaid, failed
    stripe_payment_intent_id = Column(String(255), nullable=True)
    settled_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    client = relationship("ClientAccount")
    license = relationship("SaaSLicense")
    client_sale = relationship("ClientSale")
    usage_records = relationship(
        "MeteredUsageRecord",
        back_populates="invoice",
        cascade="all, delete-orphan",
        order_by=lambda: desc(MeteredUsageRecord.recorded_at)
    )
