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

class LeadCreate(BaseModel):
    company_name: str
    company_domain: Optional[str] = None
    industry: Optional[str] = None
    contact_first_name: str
    contact_last_name: str
    contact_email: EmailStr
    contact_title: Optional[str] = None
    decision_maker_role: Optional[str] = "purchasing"

class LeadUpdate(BaseModel):
    pipeline_stage: Optional[str] = None
    lead_score: Optional[int] = None
    status: Optional[str] = None
    research_summary: Optional[str] = None

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
    created_at: datetime
    company: Optional[CompanyResponse] = None
    contact: Optional[ContactResponse] = None

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
