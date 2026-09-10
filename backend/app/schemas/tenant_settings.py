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
    
    # Stripe Payment Gateway
    stripe_publishable_key: Optional[str] = None
    has_stripe_secret: bool = False
    masked_stripe_secret: Optional[str] = None
    has_stripe_webhook_secret: bool = False
    is_payment_configured: bool = False

    # Multi-Channel Notification Gateways
    twilio_account_sid: Optional[str] = None
    has_twilio_token: bool = False
    masked_twilio_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    is_sms_configured: bool = False

    has_sendgrid_key: bool = False
    masked_sendgrid_key: Optional[str] = None
    email_from_address: Optional[str] = None
    email_from_name: Optional[str] = None
    is_email_configured: bool = False

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

    # Notification Gateways
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_from_number: Optional[str] = None
    sendgrid_api_key: Optional[str] = None
    email_from_address: Optional[str] = None
    email_from_name: Optional[str] = None

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

class TestNotificationRequest(BaseModel):
    recipient: str
    channel: str = "sms"  # sms, email
    message: Optional[str] = None
