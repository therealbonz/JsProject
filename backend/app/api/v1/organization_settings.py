import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.tenant import User, Organization
from app.schemas.tenant_settings import (
    OrganizationSettingsResponse,
    OrganizationSettingsUpdateRequest,
    PublicBrandResponse
)
from app.api.deps import get_current_tenant

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
    Returns the white-label branding and payment configuration for the authenticated tenant.
    Sensitive Stripe secret keys are masked.
    """
    user, org, _ = tenant_context

    # Re-fetch from db to ensure latest state
    stmt = select(Organization).where(Organization.id == org.id)
    res = await db.execute(stmt)
    current_org = res.scalar_one_or_none() or org

    has_secret = bool(current_org.stripe_secret_key and current_org.stripe_secret_key.strip())
    has_webhook = bool(current_org.stripe_webhook_secret and current_org.stripe_webhook_secret.strip())

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
        is_payment_configured=has_secret
    )

@router.put("/settings", response_model=OrganizationSettingsResponse)
async def update_organization_settings(
    payload: OrganizationSettingsUpdateRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates white-label branding, portal theming, support information, and merchant Stripe keys.
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
    if payload.stripe_publishable_key is not None:
        current_org.stripe_publishable_key = payload.stripe_publishable_key.strip() or None
    if payload.stripe_secret_key is not None:
        # Only update if not blank or placeholder mask
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

    await db.commit()
    await db.refresh(current_org)

    has_secret = bool(current_org.stripe_secret_key and current_org.stripe_secret_key.strip())
    has_webhook = bool(current_org.stripe_webhook_secret and current_org.stripe_webhook_secret.strip())

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
        is_payment_configured=has_secret
    )

@router.get("/public-brand/{org_id}", response_model=PublicBrandResponse)
async def get_public_brand_info(
    org_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Public sanitized branding endpoint.
    Used by public tracking and checkout portals to dynamically style customer-facing UI.
    Never exposes Stripe keys or internal operational data.
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
