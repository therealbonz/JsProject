from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, ConfigDict

class CompanyCreate(BaseModel):
    name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    employee_range: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None

class CompanyResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    domain: Optional[str]
    industry: Optional[str]
    employee_range: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    notes: Optional[str]
    research_data: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ContactCreate(BaseModel):
    company_id: str
    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    decision_maker_role: str = "other"
    is_primary: bool = False

class ContactResponse(BaseModel):
    id: str
    organization_id: str
    company_id: str
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    job_title: Optional[str]
    decision_maker_role: str
    is_primary: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CallLogCreate(BaseModel):
    caller_name: Optional[str] = None
    called_at: Optional[datetime] = None
    duration_minutes: Optional[int] = 0
    outcome: Optional[str] = "connected"
    notes: str
    next_steps: Optional[str] = None

class CallLogResponse(BaseModel):
    id: str
    organization_id: str
    lead_id: str
    company_id: Optional[str] = None
    contact_id: Optional[str] = None
    caller_name: Optional[str] = None
    called_at: datetime
    duration_minutes: Optional[int] = 0
    outcome: str
    notes: str
    next_steps: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AppointmentCreate(BaseModel):
    lead_id: str
    contact_id: Optional[str] = None
    company_id: Optional[str] = None
    title: Optional[str] = "Executive Procurement Consultation"
    scheduled_at: datetime
    duration_minutes: Optional[int] = 30
    status: Optional[str] = "scheduled"
    meeting_url: Optional[str] = None
    closer_name: Optional[str] = "Senior Sales Executive"
    closer_email: Optional[str] = None
    executive_briefing: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    booked_by_agent: Optional[bool] = True

class AppointmentUpdate(BaseModel):
    title: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    status: Optional[str] = None
    meeting_url: Optional[str] = None
    closer_name: Optional[str] = None
    closer_email: Optional[str] = None
    executive_briefing: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

class AppointmentResponse(BaseModel):
    id: str
    organization_id: str
    lead_id: str
    company_id: Optional[str] = None
    contact_id: Optional[str] = None
    title: str
    scheduled_at: datetime
    duration_minutes: int
    status: str
    meeting_url: Optional[str] = None
    closer_name: str
    closer_email: Optional[str] = None
    executive_briefing: Dict[str, Any] = {}
    notes: Optional[str] = None
    booked_by_agent: bool
    created_at: datetime
    company: Optional[CompanyResponse] = None
    contact: Optional[ContactResponse] = None

    model_config = ConfigDict(from_attributes=True)

class LeadCreate(BaseModel):
    company_name: str
    company_domain: Optional[str] = None
    industry: Optional[str] = None
    contact_first_name: str
    contact_last_name: str
    contact_email: EmailStr
    contact_title: Optional[str] = None
    decision_maker_role: Optional[str] = "purchasing"
    notes: Optional[str] = None
    last_call_at: Optional[datetime] = None
    last_call_notes: Optional[str] = None
    last_call_outcome: Optional[str] = "connected"
    call_duration_minutes: Optional[int] = 0

class LeadUpdate(BaseModel):
    pipeline_stage: Optional[str] = None
    lead_score: Optional[int] = None
    status: Optional[str] = None
    research_summary: Optional[str] = None
    notes: Optional[str] = None
    last_call_at: Optional[datetime] = None
    last_call_notes: Optional[str] = None
    last_call_outcome: Optional[str] = None

class LeadResponse(BaseModel):
    id: str
    organization_id: str
    company_id: str
    contact_id: Optional[str]
    lead_score: int
    pipeline_stage: str
    status: str
    last_contacted_at: Optional[datetime]
    next_action_at: Optional[datetime]
    next_action_type: Optional[str]
    research_summary: Optional[str]
    notes: Optional[str] = None
    last_call_at: Optional[datetime] = None
    last_call_notes: Optional[str] = None
    last_call_outcome: Optional[str] = None
    created_at: datetime
    company: Optional[CompanyResponse] = None
    contact: Optional[ContactResponse] = None
    call_logs: List[CallLogResponse] = []
    appointments: List[AppointmentResponse] = []

    model_config = ConfigDict(from_attributes=True)

class ProductCreate(BaseModel):
    name: str
    sku: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    unit_price: float
    min_allowed_price: float
    currency: str = "USD"

class ProductResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    sku: Optional[str]
    category: Optional[str]
    description: Optional[str]
    unit_price: float
    min_allowed_price: float
    currency: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)

class KnowledgeDocCreate(BaseModel):
    title: str
    category: str = "faq"
    content: str
    metadata_json: Optional[Dict[str, Any]] = None

class KnowledgeDocResponse(BaseModel):
    id: str
    organization_id: str
    title: str
    category: str
    content: str
    metadata_json: Dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ClientSaleCreate(BaseModel):
    order_number: Optional[str] = None
    amount: float
    sale_date: Optional[datetime] = None
    status: Optional[str] = "completed"
    payment_method: Optional[str] = "credit_terms_30"
    payment_status: Optional[str] = "unpaid"
    customer_email: Optional[EmailStr] = None
    customer_phone: Optional[str] = None
    auto_fulfill_on_payment: Optional[bool] = True
    items_summary: str
    sales_rep_name: Optional[str] = None
    notes: Optional[str] = None

class ClientSaleResponse(BaseModel):
    id: str
    organization_id: str
    client_id: str
    lead_id: Optional[str] = None
    order_number: str
    amount: float
    sale_date: datetime
    status: str
    payment_method: str
    payment_status: Optional[str] = "unpaid"
    stripe_checkout_url: Optional[str] = None
    stripe_session_id: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    auto_fulfill_on_payment: Optional[bool] = True
    items_summary: str
    sales_rep_name: Optional[str] = None
    notes: Optional[str] = None
    purchase_order_id: Optional[str] = None
    po_number: Optional[str] = None
    carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    shipping_status: Optional[str] = None
    destination_type: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CustomerNotificationResponse(BaseModel):
    id: str
    client_sale_id: str
    recipient: str
    channel: str
    event_type: str
    title: str
    message_body: str
    tracking_url: Optional[str] = None
    sent_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)

class StripeCheckoutCreateRequest(BaseModel):
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None
    customer_email: Optional[str] = None

class StripeCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    order_number: str
    amount: float
    is_simulation: bool

class ClientAccountCreate(BaseModel):
    account_name: str
    company_domain: Optional[str] = None
    industry: Optional[str] = None
    contact_first_name: str
    contact_last_name: str
    contact_email: EmailStr
    contact_phone: Optional[str] = None
    account_tier: Optional[str] = "standard"  # standard, premium, enterprise, vip
    status: Optional[str] = "active"
    reorder_cadence_days: Optional[int] = 30
    renewal_date: Optional[datetime] = None
    notes: Optional[str] = None

class ClientAccountUpdate(BaseModel):
    account_name: Optional[str] = None
    account_tier: Optional[str] = None
    status: Optional[str] = None
    reorder_cadence_days: Optional[int] = None
    renewal_date: Optional[datetime] = None
    account_manager: Optional[str] = None
    notes: Optional[str] = None

class ClientAccountResponse(BaseModel):
    id: str
    organization_id: str
    company_id: str
    primary_contact_id: Optional[str] = None
    account_name: str
    account_tier: str
    status: str
    total_revenue: float
    order_count: int
    contract_start_date: Optional[datetime] = None
    renewal_date: Optional[datetime] = None
    reorder_cadence_days: int
    next_reorder_date: Optional[datetime] = None
    account_manager: str
    notes: Optional[str] = None
    stripe_customer_id: Optional[str] = None
    has_payment_method_on_file: bool = False
    card_brand: Optional[str] = None
    card_last4: Optional[str] = None
    auto_charge_enabled: bool = False
    auto_charge_limit: Optional[float] = None
    payment_method_type: Optional[str] = "card"
    portal_access_token: Optional[str] = None
    predicted_burn_rate: Optional[float] = 0.0
    safety_stock_buffer_percent: Optional[float] = 15.0
    stockout_risk_score: Optional[int] = 10
    stockout_risk_level: Optional[str] = "low"
    recommended_reorder_date: Optional[datetime] = None
    forecast_confidence: Optional[float] = 0.85
    forecast_rationale: Optional[str] = None
    forecast_updated_at: Optional[datetime] = None
    created_at: datetime
    company: Optional[CompanyResponse] = None
    primary_contact: Optional[ContactResponse] = None
    sales: List[ClientSaleResponse] = []

    model_config = ConfigDict(from_attributes=True)

class AttachPaymentMethodRequest(BaseModel):
    card_brand: Optional[str] = "visa"
    card_last4: Optional[str] = "4242"
    payment_method_type: Optional[str] = "card"
    enable_auto_charge: Optional[bool] = True
    auto_charge_limit: Optional[float] = None

class AutoChargeToggleRequest(BaseModel):
    auto_charge_enabled: Optional[bool] = None
    enabled: Optional[bool] = None
    auto_charge_limit: Optional[float] = None
    limit: Optional[float] = None

class SetupPaymentMethodResponse(BaseModel):
    client_id: str
    stripe_customer_id: str
    setup_url: Optional[str] = None
    client_secret: Optional[str] = None
    mode: str = "simulated"

class ClientSalesOverviewStats(BaseModel):
    total_revenue: float
    active_clients_count: int
    total_orders_count: int
    average_order_value: float

class LeadConversionPayload(BaseModel):
    account_tier: Optional[str] = "standard"
    reorder_cadence_days: Optional[int] = 30
    initial_order_amount: Optional[float] = None
    initial_order_items: Optional[str] = None
    notes: Optional[str] = None

class DemandForecastResponse(BaseModel):
    client_id: str
    account_name: str
    predicted_burn_rate: float
    reorder_cadence_days: int
    recommended_cadence_days: int
    next_reorder_date: Optional[datetime] = None
    recommended_reorder_date: Optional[datetime] = None
    days_until_stockout: int
    stockout_risk_score: int
    stockout_risk_level: str
    safety_stock_buffer_percent: float
    recommended_restock_amount: float
    forecast_confidence: float
    forecast_rationale: str
    model_used: str
    telemetry: Dict[str, Any]
    last_updated: datetime

class DemandForecastOverviewStats(BaseModel):
    monitored_accounts: int
    high_risk_accounts: int
    moderate_risk_accounts: int
    safe_accounts: int
    average_burn_rate: float
    projected_30d_demand: float
    average_forecast_confidence: float

class ApplyForecastCadenceRequest(BaseModel):
    apply_cadence_days: Optional[bool] = True
    apply_reorder_date: Optional[bool] = True
