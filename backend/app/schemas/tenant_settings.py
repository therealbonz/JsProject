from typing import Optional
from pydantic import BaseModel, ConfigDict

class OrganizationSettingsResponse(BaseModel):
    id: str
    name: str
    slug: str
    brand_name: Optional[str] = None
    brand_logo_url: Optional[str] = None
    brand_accent_color: Optional[str] = "#4f46e5"
    support_email: Optional[str] = None
    support_phone: Optional[str] = None
    custom_footer_text: Optional[str] = None
    tracking_portal_notice: Optional[str] = None
    stripe_publishable_key: Optional[str] = None
    has_stripe_secret: bool = False
    masked_stripe_secret: Optional[str] = None
    has_stripe_webhook_secret: bool = False
    is_payment_configured: bool = False

    model_config = ConfigDict(from_attributes=True)

class OrganizationSettingsUpdateRequest(BaseModel):
    name: Optional[str] = None
    brand_name: Optional[str] = None
    brand_logo_url: Optional[str] = None
    brand_accent_color: Optional[str] = None
    support_email: Optional[str] = None
    support_phone: Optional[str] = None
    custom_footer_text: Optional[str] = None
    tracking_portal_notice: Optional[str] = None
    stripe_publishable_key: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None

class PublicBrandResponse(BaseModel):
    org_id: str
    name: str
    brand_name: str
    brand_logo_url: Optional[str] = None
    brand_accent_color: str = "#4f46e5"
    support_email: Optional[str] = None
    support_phone: Optional[str] = None
    custom_footer_text: Optional[str] = None
    tracking_portal_notice: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
