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
    items_summary: str
    sales_rep_name: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

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
    created_at: datetime
    company: Optional[CompanyResponse] = None
    primary_contact: Optional[ContactResponse] = None
    sales: List[ClientSaleResponse] = []

    model_config = ConfigDict(from_attributes=True)

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
