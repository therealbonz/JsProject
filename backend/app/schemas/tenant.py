from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    status: str

    model_config = ConfigDict(from_attributes=True)

class AIConfigUpdate(BaseModel):
    company_name: Optional[str] = None
    company_description: Optional[str] = None
    autonomy_level: Optional[str] = None
    max_discount_pct: Optional[float] = None
    tone_of_voice: Optional[str] = None
    prohibited_phrases: Optional[List[str]] = None
    sales_guidelines: Optional[str] = None
    hitl_required_for_closing: Optional[bool] = None
    business_hours: Optional[Dict[str, Any]] = None

class AIConfigResponse(BaseModel):
    id: str
    organization_id: str
    company_name: Optional[str]
    company_description: Optional[str]
    autonomy_level: str
    max_discount_pct: float
    tone_of_voice: str
    prohibited_phrases: List[str]
    sales_guidelines: Optional[str]
    hitl_required_for_closing: bool

    model_config = ConfigDict(from_attributes=True)
