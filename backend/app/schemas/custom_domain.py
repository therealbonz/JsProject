from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field

class CustomDomainBase(BaseModel):
    domain: str = Field(..., description="Fully qualified domain or subdomain, e.g. portal.acme.com")
    verification_method: str = Field("cname", description="Verification strategy: 'cname' or 'txt'")
    custom_theme_overrides: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Optional domain-specific brand and theme overrides")

class CustomDomainCreate(CustomDomainBase):
    pass

class CustomDomainUpdate(BaseModel):
    is_primary: Optional[bool] = None
    is_active: Optional[bool] = None
    custom_theme_overrides: Optional[Dict[str, Any]] = None

class CustomDomainResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    domain: str
    cname_target: str
    verification_token: str
    verification_method: str
    verification_status: str
    verified_at: Optional[datetime] = None
    is_primary: bool
    ssl_status: str
    ssl_provisioned_at: Optional[datetime] = None
    dns_check_payload: Dict[str, Any] = Field(default_factory=dict)
    last_checked_at: Optional[datetime] = None
    is_active: bool
    custom_theme_overrides: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    cname_instruction: Optional[str] = None
    txt_instruction: Optional[str] = None

class DomainVerificationResult(BaseModel):
    success: bool
    verification_status: str
    verification_method: str
    resolved_target: Optional[str] = None
    resolved_txt: List[str] = Field(default_factory=list)
    message: str
    dns_check_payload: Dict[str, Any] = Field(default_factory=dict)

class PublicDomainResolutionResponse(BaseModel):
    is_custom_domain: bool
    domain: str
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    brand_name: Optional[str] = None
    brand_logo_url: Optional[str] = None
    brand_accent_color: Optional[str] = None
    support_email: Optional[str] = None
    support_phone: Optional[str] = None
    custom_footer_text: Optional[str] = None
    tracking_portal_notice: Optional[str] = None
    ssl_active: bool = False

class NginxConfigResponse(BaseModel):
    domain: str
    nginx_server_block: str
    certbot_command: str
    config_filename: str
