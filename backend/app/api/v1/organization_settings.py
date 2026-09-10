import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.models.tenant import User, Organization
from app.models.crm import CustomerNotification
from app.schemas.tenant_settings import (
    OrganizationSettingsResponse,
    OrganizationSettingsUpdateRequest,
    PublicBrandResponse,
    TestNotificationRequest
)
from app.api.deps import get_current_tenant
from app.services.communication_gateway import TwilioSMSGateway, EmailNotificationGateway

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orgs", tags=["Organization & White-Label Settings"])

def _mask_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    if len(key) <= 8:
        return "••••••••"
    return f"{key[:7]}••••••••{key[-4:]}"

@router.get("/settings", response_model=OrganizationSettingsResponse)
async def get_organization_settings(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns the white-label branding, Stripe, Twilio, and SendGrid configurations.
    Sensitive tokens are masked.
    """
    user, org, _ = tenant_context

    stmt = select(Organization).where(Organization.id == org.id)
    res = await db.execute(stmt)
    current_org = res.scalar_one_or_none() or org

    has_secret = bool(current_org.stripe_secret_key and current_org.stripe_secret_key.strip())
    has_webhook = bool(current_org.stripe_webhook_secret and current_org.stripe_webhook_secret.strip())
    has_twilio = bool(current_org.twilio_auth_token and current_org.twilio_auth_token.strip())
    has_sendgrid = bool(current_org.sendgrid_api_key and current_org.sendgrid_api_key.strip())

    return OrganizationSettingsResponse(
        id=current_org.id,
        name=current_org.name,
        slug=current_org.slug,
        brand_name=current_org.brand_name or current_org.name,
        brand_logo_url=current_org.brand_logo_url,
        brand_accent_color=current_org.brand_accent_color or "#4f46e5",
        support_email=current_org.support_email,
        support_phone=current_org.support_phone,
        custom_footer_text=current_org.custom_footer_text,
        tracking_portal_notice=current_org.tracking_portal_notice,
        stripe_publishable_key=current_org.stripe_publishable_key,
        has_stripe_secret=has_secret,
        masked_stripe_secret=_mask_key(current_org.stripe_secret_key) if has_secret else None,
        has_stripe_webhook_secret=has_webhook,
        is_payment_configured=has_secret,
        twilio_account_sid=current_org.twilio_account_sid,
        has_twilio_token=has_twilio,
        masked_twilio_token=_mask_key(current_org.twilio_auth_token) if has_twilio else None,
        twilio_from_number=current_org.twilio_from_number,
        is_sms_configured=bool(current_org.twilio_account_sid and has_twilio and current_org.twilio_from_number),
        has_sendgrid_key=has_sendgrid,
        masked_sendgrid_key=_mask_key(current_org.sendgrid_api_key) if has_sendgrid else None,
        email_from_address=current_org.email_from_address,
        email_from_name=current_org.email_from_name,
        is_email_configured=has_sendgrid
    )

@router.put("/settings", response_model=OrganizationSettingsResponse)
async def update_organization_settings(
    payload: OrganizationSettingsUpdateRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates white-label branding, portal theming, and payment/communication gateway credentials.
    """
    user, org, _ = tenant_context

    stmt = select(Organization).where(Organization.id == org.id)
    res = await db.execute(stmt)
    current_org = res.scalar_one_or_none()
    if not current_org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if payload.name is not None and payload.name.strip():
        current_org.name = payload.name.strip()
    if payload.brand_name is not None:
        current_org.brand_name = payload.brand_name.strip() or None
    if payload.brand_logo_url is not None:
        current_org.brand_logo_url = payload.brand_logo_url.strip() or None
    if payload.brand_accent_color is not None:
        color = payload.brand_accent_color.strip()
        if color and not color.startswith("#"):
            color = f"#{color}"
        current_org.brand_accent_color = color or "#4f46e5"
    if payload.support_email is not None:
        current_org.support_email = payload.support_email.strip() or None
    if payload.support_phone is not None:
        current_org.support_phone = payload.support_phone.strip() or None
    if payload.custom_footer_text is not None:
        current_org.custom_footer_text = payload.custom_footer_text.strip() or None
    if payload.tracking_portal_notice is not None:
        current_org.tracking_portal_notice = payload.tracking_portal_notice.strip() or None

    # Stripe credentials
    if payload.stripe_publishable_key is not None:
        current_org.stripe_publishable_key = payload.stripe_publishable_key.strip() or None
    if payload.stripe_secret_key is not None:
        val = payload.stripe_secret_key.strip()
        if val and "••••" not in val:
            current_org.stripe_secret_key = val
        elif val == "":
            current_org.stripe_secret_key = None
    if payload.stripe_webhook_secret is not None:
        val = payload.stripe_webhook_secret.strip()
        if val and "••••" not in val:
            current_org.stripe_webhook_secret = val
        elif val == "":
            current_org.stripe_webhook_secret = None

    # Twilio SMS credentials
    if payload.twilio_account_sid is not None:
        current_org.twilio_account_sid = payload.twilio_account_sid.strip() or None
    if payload.twilio_auth_token is not None:
        val = payload.twilio_auth_token.strip()
        if val and "••••" not in val:
            current_org.twilio_auth_token = val
        elif val == "":
            current_org.twilio_auth_token = None
    if payload.twilio_from_number is not None:
        current_org.twilio_from_number = payload.twilio_from_number.strip() or None

    # SendGrid Email credentials
    if payload.sendgrid_api_key is not None:
        val = payload.sendgrid_api_key.strip()
        if val and "••••" not in val:
            current_org.sendgrid_api_key = val
        elif val == "":
            current_org.sendgrid_api_key = None
    if payload.email_from_address is not None:
        current_org.email_from_address = payload.email_from_address.strip() or None
    if payload.email_from_name is not None:
        current_org.email_from_name = payload.email_from_name.strip() or None

    await db.commit()
    await db.refresh(current_org)

    has_secret = bool(current_org.stripe_secret_key and current_org.stripe_secret_key.strip())
    has_webhook = bool(current_org.stripe_webhook_secret and current_org.stripe_webhook_secret.strip())
    has_twilio = bool(current_org.twilio_auth_token and current_org.twilio_auth_token.strip())
    has_sendgrid = bool(current_org.sendgrid_api_key and current_org.sendgrid_api_key.strip())

    return OrganizationSettingsResponse(
        id=current_org.id,
        name=current_org.name,
        slug=current_org.slug,
        brand_name=current_org.brand_name or current_org.name,
        brand_logo_url=current_org.brand_logo_url,
        brand_accent_color=current_org.brand_accent_color or "#4f46e5",
        support_email=current_org.support_email,
        support_phone=current_org.support_phone,
        custom_footer_text=current_org.custom_footer_text,
        tracking_portal_notice=current_org.tracking_portal_notice,
        stripe_publishable_key=current_org.stripe_publishable_key,
        has_stripe_secret=has_secret,
        masked_stripe_secret=_mask_key(current_org.stripe_secret_key) if has_secret else None,
        has_stripe_webhook_secret=has_webhook,
        is_payment_configured=has_secret,
        twilio_account_sid=current_org.twilio_account_sid,
        has_twilio_token=has_twilio,
        masked_twilio_token=_mask_key(current_org.twilio_auth_token) if has_twilio else None,
        twilio_from_number=current_org.twilio_from_number,
        is_sms_configured=bool(current_org.twilio_account_sid and has_twilio and current_org.twilio_from_number),
        has_sendgrid_key=has_sendgrid,
        masked_sendgrid_key=_mask_key(current_org.sendgrid_api_key) if has_sendgrid else None,
        email_from_address=current_org.email_from_address,
        email_from_name=current_org.email_from_name,
        is_email_configured=has_sendgrid
    )

@router.post("/notifications/test-sms")
async def test_sms_gateway(
    payload: TestNotificationRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Sends a test SMS to verify Twilio configuration (or simulation mode).
    """
    user, org, _ = tenant_context
    msg = payload.message or f"Test SMS alert from {org.brand_name or org.name}: Multi-channel gateway active and verified."
    res = await TwilioSMSGateway.send_sms(to_phone=payload.recipient, message=msg, org=org)
    return res

@router.post("/notifications/test-email")
async def test_email_gateway(
    payload: TestNotificationRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Sends a test branded HTML email to verify SendGrid configuration (or simulation mode).
    """
    user, org, _ = tenant_context
    brand_name = org.brand_name or org.name
    msg = payload.message or f"This is a test transactional message verifying your live notification gateway for {brand_name}."
    html = EmailNotificationGateway.render_branded_email_html(
        title=f"Test Gateway Verification • {brand_name}",
        message_body=msg,
        org=org,
        cta_url=f"https://therealbonz.com/JsProject/",
        cta_text="Access Client Portal",
        order_number="TEST-VERIFICATION"
    )
    res = await EmailNotificationGateway.send_email(
        to_email=payload.recipient,
        subject=f"Test Verification: {brand_name} Gateway",
        html_content=html,
        org=org
    )
    return res

@router.get("/notifications/history")
async def get_notification_history(
    limit: int = 50,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns recent customer notification dispatch history for the tenant.
    """
    user, org, _ = tenant_context
    stmt = (
        select(CustomerNotification)
        .where(CustomerNotification.organization_id == org.id)
        .order_by(desc(CustomerNotification.sent_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    notifications = res.scalars().all()
    return notifications

@router.get("/public-brand/{org_id}", response_model=PublicBrandResponse)
async def get_public_brand_info(
    org_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Public sanitized branding endpoint.
    Used by public tracking and checkout portals to dynamically style customer-facing UI.
    Never exposes Stripe/Twilio keys or internal operational data.
    """
    stmt = select(Organization).where(Organization.id == org_id)
    res = await db.execute(stmt)
    org = res.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization brand not found")

    return PublicBrandResponse(
        org_id=org.id,
        name=org.name,
        brand_name=org.brand_name or org.name,
        brand_logo_url=org.brand_logo_url,
        brand_accent_color=org.brand_accent_color or "#4f46e5",
        support_email=org.support_email,
        support_phone=org.support_phone,
        custom_footer_text=org.custom_footer_text,
        tracking_portal_notice=org.tracking_portal_notice
    )
