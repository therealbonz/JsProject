from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class SaaSLicenseBase(BaseModel):
    client_id: str
    product_name: Optional[str] = "Enterprise AI Platform"
    plan_tier: Optional[str] = "pro"  # starter, pro, enterprise, custom
    billing_interval: Optional[str] = "annual"  # monthly, quarterly, annual, multi_year
    seat_unit_price: Optional[float] = 50.0
    licensed_seats: Optional[int] = 25
    monthly_quota_units: Optional[int] = 100000
    overage_allowed: Optional[bool] = True
    overage_unit_rate: Optional[float] = 0.05
    auto_renew: Optional[bool] = True
    features_enabled: Optional[List[str]] = Field(default_factory=lambda: ["hitl_guardrails", "ai_order_filler", "api_access"])
    notes: Optional[str] = None

class SaaSLicenseCreate(SaaSLicenseBase):
    pass

class SaaSLicenseUpdate(BaseModel):
    product_name: Optional[str] = None
    plan_tier: Optional[str] = None
    license_status: Optional[str] = None
    billing_interval: Optional[str] = None
    seat_unit_price: Optional[float] = None
    licensed_seats: Optional[int] = None
    monthly_quota_units: Optional[int] = None
    overage_allowed: Optional[bool] = None
    overage_unit_rate: Optional[float] = None
    auto_renew: Optional[bool] = None
    features_enabled: Optional[List[str]] = None
    notes: Optional[str] = None

class SaaSLicenseResponse(BaseModel):
    id: str
    organization_id: str
    client_id: str
    company_id: str
    primary_contact_id: Optional[str] = None

    company_name: Optional[str] = None
    client_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None

    license_key: str
    license_token: Optional[str] = None
    product_name: str
    plan_tier: str
    license_status: str
    billing_interval: str

    seat_unit_price: float
    licensed_seats: int
    active_seats_used: int
    seat_utilization_pct: float

    monthly_quota_units: int
    current_quota_used: int
    overage_allowed: bool
    overage_unit_rate: float

    mrr: float
    arr: float

    auto_renew: bool
    contract_start_date: datetime
    renewal_date: datetime
    days_until_renewal: Optional[int] = None
    last_telemetry_at: Optional[datetime] = None

    health_score: int
    churn_risk_level: str
    health_rationale: Optional[str] = None

    features_enabled: List[str] = []
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class SaaSTelemetryPingRequest(BaseModel):
    active_seats: int = Field(..., ge=0, description="Current number of active user seats")
    quota_used: int = Field(..., ge=0, description="Monthly API or resource quota units consumed")
    daily_active_users: Optional[int] = None
    api_calls_count: Optional[int] = None

class SaaSExpansionAuditItem(BaseModel):
    license_id: str
    license_key: str
    client_name: str
    plan_tier: str
    licensed_seats: int
    active_seats_used: int
    seat_utilization_pct: float
    current_mrr: float
    proposed_new_seats: int
    proposed_new_mrr: float
    arr_delta: float
    discount_pct: float
    requires_hitl: bool
    ai_drafted_outreach: str
    proposal_id: Optional[str] = None

class SaaSExpansionAuditResponse(BaseModel):
    total_licenses_scanned: int
    expansion_candidates_found: int
    proposals_generated: List[SaaSExpansionAuditItem]

class SaaSRenewalScanItem(BaseModel):
    license_id: str
    license_key: str
    client_name: str
    renewal_date: datetime
    days_until_renewal: int
    health_score: int
    churn_risk_level: str
    arr: float
    action_recommended: str
    auto_charged: bool = False
    renewal_sale_id: Optional[str] = None

class SaaSRenewalScanResponse(BaseModel):
    total_licenses_scanned: int
    expiring_soon_count: int
    at_risk_count: int
    items: List[SaaSRenewalScanItem]

class SaaSCloudProvisionRequest(BaseModel):
    cloud_provider: Optional[str] = "amazon_aws"  # amazon_aws, digikey_hardware, grainger_infra, custom_cloud
    resource_spec: Optional[str] = None

class SaaSCloudProvisionResponse(BaseModel):
    license_id: str
    license_key: str
    purchase_order_id: str
    po_number: str
    supplier_name: str
    provisioning_status: str
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    message: str

class SaaSOverviewMetrics(BaseModel):
    total_licenses: int
    active_licenses: int
    total_arr: float
    total_mrr: float
    total_licensed_seats: int
    total_active_seats: int
    avg_seat_utilization_pct: float
    healthy_count: int
    monitor_count: int
    at_risk_count: int
    critical_count: int
