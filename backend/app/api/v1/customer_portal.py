import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.tenant import User, Organization
from app.models.crm import ClientAccount, ClientSale
from app.api.deps import get_current_tenant
from app.services.stripe_recurring_service import StripeRecurringService
from app.services.replenishment_service import ReplenishmentService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Customer Self-Service Portal"])

# Schemas
class PortalCadenceUpdateRequest(BaseModel):
    reorder_cadence_days: Optional[int] = Field(None, ge=1, le=365)
    snooze_days: Optional[int] = Field(None, ge=1, le=180)

class PortalPaymentMethodRequest(BaseModel):
    card_brand: Optional[str] = "visa"
    card_last4: Optional[str] = "4242"
    payment_method_type: Optional[str] = "card"
    enable_auto_charge: Optional[bool] = True
    auto_charge_limit: Optional[float] = None

# Helper to find client by portal token
async def get_client_by_portal_token(
    token: str,
    db: AsyncSession
) -> ClientAccount:
    stmt = (
        select(ClientAccount)
        .options(
            selectinload(ClientAccount.primary_contact),
            selectinload(ClientAccount.company),
            selectinload(ClientAccount.sales).selectinload(ClientSale.purchase_orders)
        )
        .where(ClientAccount.portal_access_token == token)
    )
    res = await db.execute(stmt)
    client = res.scalar_one_or_none()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired customer portal access link."
        )
    return client

# 1. Tenant authenticated endpoint to generate or get a client's magic link
@router.post("/crm/clients/{client_id}/portal-link")
async def generate_client_portal_link(
    client_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates or retrieves a secure, passwordless customer portal access link for an active client account.
    """
    _, org, _ = tenant_context
    stmt = select(ClientAccount).where(
        ClientAccount.id == client_id,
        ClientAccount.organization_id == org.id
    )
    res = await db.execute(stmt)
    client = res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")

    if not client.portal_access_token:
        client.portal_access_token = f"pt_{secrets.token_urlsafe(24)}"
        await db.commit()
        await db.refresh(client)

    token = client.portal_access_token
    portal_path = f"/portal/{token}"
    full_url = f"https://therealbonz.com/JsProject/portal/{token}"

    return {
        "client_id": client.id,
        "account_name": client.account_name,
        "portal_access_token": token,
        "portal_path": portal_path,
        "full_portal_url": full_url
    }

# 2. Public / Passwordless session loader by magic token
@router.get("/portal/session/{token}")
async def get_customer_portal_session(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Validates the customer's portal magic link token and returns the account overview,
    scheduled replenishment status, payment method preferences, and past orders ledger.
    """
    client = await get_client_by_portal_token(token=token, db=db)

    # Load host tenant organization for white-label styling
    org_stmt = select(Organization).where(Organization.id == client.organization_id)
    org_res = await db.execute(org_stmt)
    org = org_res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    days_until_reorder = None
    if client.next_reorder_date:
        nr = client.next_reorder_date
        if nr.tzinfo is None:
            nr = nr.replace(tzinfo=timezone.utc)
        days_until_reorder = (nr.date() - now.date()).days

    # Identify any open replenishment proposal
    pending_proposal = None
    for s in (client.sales or []):
        if s.status == "replenishment_pending" and s.payment_status == "unpaid":
            pending_proposal = {
                "sale_id": s.id,
                "order_number": s.order_number,
                "amount": s.amount,
                "items_summary": s.items_summary,
                "checkout_url": s.stripe_checkout_url,
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            break

    # Build sales transactions ledger with printable document URLs
    sales_history = []
    for s in (client.sales or []):
        po = s.purchase_orders[0] if s.purchase_orders else None
        sales_history.append({
            "sale_id": s.id,
            "order_number": s.order_number,
            "amount": s.amount,
            "sale_date": s.sale_date.isoformat() if s.sale_date else None,
            "status": s.status,
            "payment_status": s.payment_status,
            "payment_method": s.payment_method,
            "items_summary": s.items_summary,
            "po_number": po.po_number if po else None,
            "carrier": po.carrier if po else None,
            "tracking_number": po.tracking_number if po else None,
            "shipping_status": po.shipping_status if po else ("delivered" if s.status == "completed" else "pending"),
            "tracking_url": f"/track/{s.order_number}",
            "invoice_url": f"/api/v1/documents/invoice/{s.id}?print=true",
            "packing_slip_url": f"/api/v1/documents/packing-slip/{s.id}?print=true"
        })

    return {
        "tenant": {
            "brand_name": org.brand_name if org and org.brand_name else (org.name if org else "B2B Supply Co"),
            "brand_logo_url": org.brand_logo_url if org else None,
            "brand_accent_color": org.brand_accent_color if org and org.brand_accent_color else "#4f46e5",
            "support_email": org.support_email if org else "support@therealbonz.com",
            "support_phone": org.support_phone if org else "+1 (800) 555-0199",
            "custom_footer_text": org.custom_footer_text if org else "Enterprise Automated Restock & Supply Chain Portal"
        },
        "account": {
            "id": client.id,
            "account_name": client.account_name,
            "account_tier": client.account_tier,
            "reorder_cadence_days": client.reorder_cadence_days,
            "next_reorder_date": client.next_reorder_date.isoformat() if client.next_reorder_date else None,
            "days_until_reorder": days_until_reorder,
            "total_revenue": client.total_revenue,
            "order_count": client.order_count,
            "contact_name": f"{client.primary_contact.first_name} {client.primary_contact.last_name}" if client.primary_contact else "Procurement Lead",
            "contact_email": client.primary_contact.email if client.primary_contact else None,
            "contact_phone": client.primary_contact.phone if client.primary_contact else None,
            "company_name": client.company.name if client.company else client.account_name,
            "delivery_address": client.company.address if client.company else f"{client.account_name} Receiving Facility"
        },
        "payment_method": {
            "has_payment_method_on_file": bool(client.has_payment_method_on_file),
            "card_brand": client.card_brand,
            "card_last4": client.card_last4,
            "auto_charge_enabled": bool(client.auto_charge_enabled),
            "auto_charge_limit": client.auto_charge_limit,
            "payment_method_type": client.payment_method_type or "card"
        },
        "pending_replenishment": pending_proposal,
        "sales_ledger": sales_history
    }

# 3. Update replenishment schedule or snooze restock
@router.post("/portal/session/{token}/cadence")
async def update_portal_cadence(
    token: str,
    payload: PortalCadenceUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Allows the customer to modify their recurring delivery cadence or snooze their next order date.
    """
    client = await get_client_by_portal_token(token=token, db=db)
    now = datetime.now(timezone.utc)

    if payload.reorder_cadence_days is not None:
        client.reorder_cadence_days = payload.reorder_cadence_days

    if payload.snooze_days is not None:
        base_date = client.next_reorder_date or now
        if base_date.tzinfo is None:
            base_date = base_date.replace(tzinfo=timezone.utc)
        if base_date < now:
            base_date = now
        client.next_reorder_date = base_date + timedelta(days=payload.snooze_days)

    await db.commit()
    await db.refresh(client)

    return {
        "success": True,
        "reorder_cadence_days": client.reorder_cadence_days,
        "next_reorder_date": client.next_reorder_date.isoformat() if client.next_reorder_date else None,
        "message": "Replenishment schedule updated successfully."
    }

# 4. Attach or update stored corporate card on file
@router.post("/portal/session/{token}/payment-method")
async def update_portal_payment_method(
    token: str,
    payload: PortalPaymentMethodRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Allows customer procurement to authorize and attach a corporate card for automated recurring restocks.
    """
    client = await get_client_by_portal_token(token=token, db=db)

    updated = await StripeRecurringService.attach_payment_method(
        db=db,
        client=client,
        card_brand=payload.card_brand or "visa",
        card_last4=payload.card_last4 or "4242",
        payment_method_type=payload.payment_method_type or "card",
        enable_auto_charge=payload.enable_auto_charge if payload.enable_auto_charge is not None else True,
        auto_charge_limit=payload.auto_charge_limit
    )

    return {
        "success": True,
        "has_payment_method_on_file": updated.has_payment_method_on_file,
        "card_brand": updated.card_brand,
        "card_last4": updated.card_last4,
        "auto_charge_enabled": updated.auto_charge_enabled,
        "auto_charge_limit": updated.auto_charge_limit,
        "message": f"Corporate {updated.card_brand.upper()} ending in {updated.card_last4} stored on file."
    }

# 5. Detach stored card
@router.delete("/portal/session/{token}/payment-method")
async def detach_portal_payment_method(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Allows customer to remove payment method on file and disable automated recurring charging.
    """
    client = await get_client_by_portal_token(token=token, db=db)
    updated = await StripeRecurringService.detach_payment_method(db=db, client=client)

    return {
        "success": True,
        "has_payment_method_on_file": False,
        "auto_charge_enabled": False,
        "message": "Payment method removed. Automated replenishment billing paused."
    }

# 6. Accelerate restock (Ship Restock Now)
@router.post("/portal/session/{token}/accelerate-restock")
async def accelerate_portal_restock(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Instantly initiates a restock order without waiting for the scheduled reorder date.
    If the client has auto-charge authorized, automatically executes payment and triggers supplier dropshipping.
    """
    client = await get_client_by_portal_token(token=token, db=db)

    proposal = await ReplenishmentService.generate_replenishment_proposal(
        db=db,
        org_id=client.organization_id,
        client_id=client.id
    )

    return {
        "success": True,
        "order_number": proposal.get("order_number"),
        "amount": proposal.get("amount"),
        "auto_charged": proposal.get("auto_charged", False),
        "checkout_url": proposal.get("checkout_url"),
        "message": "Restock order processed! Autonomous dropshipping initiated." if proposal.get("auto_charged") else "Restock proposal generated. Please complete payment to dispatch."
    }
