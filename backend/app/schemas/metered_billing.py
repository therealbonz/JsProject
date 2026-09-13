from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

class UsageRecordCreate(BaseModel):
    license_id: str = Field(..., description="SaaS License ID")
    metric_name: str = Field(..., description="Metric key: api_calls, ai_agent_runs, procurement_orders, edi_transactions, storage_mb")
    quantity: float = Field(1.0, ge=0.0, description="Quantity consumed")
    idempotency_key: Optional[str] = Field(None, description="Optional unique client deduplication key")
    source: Optional[str] = Field("api_gateway", description="Origin source of the event")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom event metadata")


class UsageBatchCreate(BaseModel):
    license_id: str = Field(..., description="SaaS License ID")
    events: List[UsageRecordCreate] = Field(..., description="List of usage events to ingest")


class UsageRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    license_id: str
    client_id: str
    metric_name: str
    quantity: float
    idempotency_key: Optional[str] = None
    recorded_at: datetime
    status: str = "recorded"


class MetricAllowanceDetail(BaseModel):
    metric_name: str
    display_name: str
    unit_label: str
    included_units: float
    consumed_units: float
    overage_units: float
    unit_overage_rate: float
    accrued_charge: float
    utilization_pct: float


class MeteredBillingSummaryResponse(BaseModel):
    license_id: str
    license_key: str
    client_id: str
    client_name: str
    plan_tier: str
    cycle_start: datetime
    cycle_end: datetime
    days_remaining_in_cycle: int
    metrics: List[MetricAllowanceDetail]
    total_accrued_overage: float
    projected_cycle_overage: float


class SettleCycleRequest(BaseModel):
    auto_charge: bool = Field(True, description="Whether to automatically charge client's card on file if available")
    notes: Optional[str] = Field(None, description="Optional audit settlement notes")


class MeteredInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_number: str
    license_id: str
    client_id: str
    client_name: Optional[str] = None
    cycle_start: datetime
    cycle_end: datetime
    status: str
    line_items: List[Dict[str, Any]]
    subtotal_overage_amount: float
    tax_amount: float
    total_billed_amount: float
    payment_method: str
    payment_status: str
    client_sale_id: Optional[str] = None
    settled_at: datetime
    notes: Optional[str] = None


class MetricCatalogItem(BaseModel):
    metric_name: str
    display_name: str
    unit_label: str
    description: str
    starter_included: float
    pro_included: float
    enterprise_included: float
    starter_rate: float
    pro_rate: float
    enterprise_rate: float
