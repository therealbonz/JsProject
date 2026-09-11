import os
import uuid
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.config import settings
from app.models.tenant import User, Organization
from app.models.crm import ClientSale, ClientAccount
from app.schemas.crm import StripeCheckoutCreateRequest, StripeCheckoutResponse
from app.services.order_filler.agent import OrderFillerAgent
from app.services.notification_service import NotificationService
from app.services.replenishment_service import ReplenishmentService
from app.services.webhook_service import WebhookService
from app.api.deps import get_current_tenant

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Payments & Invoicing"])

@router.post("/crm/sales/{sale_id}/create-checkout", response_model=StripeCheckoutResponse)
async def create_stripe_checkout(
    sale_id: str,
    payload: StripeCheckoutCreateRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a hosted Stripe Checkout session (or local-first simulated session) for a client sale.
    """
    user, org, _ = tenant_context
    stmt = (
        select(ClientSale)
        .options(selectinload(ClientSale.client))
        .where(
            ClientSale.id == sale_id,
            ClientSale.organization_id == org.id
        )
    )
    result = await db.execute(stmt)
    sale = result.scalar_one_or_none()

    if not sale:
        raise HTTPException(status_code=404, detail="Client sale not found")

    if payload.customer_email:
        sale.customer_email = payload.customer_email

    stripe_key = org.stripe_secret_key or getattr(settings, "STRIPE_SECRET_KEY", None)
    is_simulation = not bool(stripe_key and str(stripe_key).startswith("sk_"))

    session_id = f"cs_test_{uuid.uuid4().hex[:20]}"
    checkout_url = f"/checkout/pay/{session_id}"

    if not is_simulation:
        try:
            import stripe
            stripe.api_key = stripe_key
            success_url = payload.success_url or f"https://therealbonz.com/JsProject/track/{sale.order_number}?session_id={{CHECKOUT_SESSION_ID}}"
            cancel_url = payload.cancel_url or f"https://therealbonz.com/JsProject/track/{sale.order_number}?cancelled=true"
            
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Order #{sale.order_number}",
                            "description": sale.items_summary[:200],
                        },
                        "unit_amount": int(round(sale.amount * 100)),
                    },
                    "quantity": 1,
                }],
                mode="payment",
                customer_email=sale.customer_email,
                client_reference_id=sale.id,
                metadata={
                    "sale_id": sale.id,
                    "organization_id": org.id,
                    "order_number": sale.order_number,
                },
                success_url=success_url,
                cancel_url=cancel_url,
            )
            session_id = session.id
            checkout_url = session.url
        except Exception as e:
            logger.warning(f"Stripe API failed ({e}), falling back to local simulation session")
            is_simulation = True

    sale.stripe_session_id = session_id
    sale.stripe_checkout_url = checkout_url
    await db.commit()
    await db.refresh(sale)

    return StripeCheckoutResponse(
        checkout_url=checkout_url,
        session_id=session_id,
        order_number=sale.order_number,
        amount=sale.amount,
        is_simulation=is_simulation
    )

@router.post("/crm/sales/{sale_id}/simulate-payment")
async def simulate_customer_payment(
    sale_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Test trigger: Simulates a customer paying their invoice online.
    Triggers immediate payment status update and autonomous order bot dropshipping.
    """
    user, org, _ = tenant_context
    stmt = (
        select(ClientSale)
        .options(
            selectinload(ClientSale.client).selectinload(ClientAccount.company),
            selectinload(ClientSale.purchase_orders)
        )
        .where(
            ClientSale.id == sale_id,
            ClientSale.organization_id == org.id
        )
    )
    result = await db.execute(stmt)
    sale = result.scalar_one_or_none()

    if not sale:
        raise HTTPException(status_code=404, detail="Client sale not found")

    sale.payment_status = "paid"
    await ReplenishmentService.advance_client_cadence_on_payment(db=db, sale=sale)
    await db.commit()
    await db.refresh(sale)

    # 1. Dispatch Payment Received Notification
    await NotificationService.create_and_send_notification(
        db=db,
        sale=sale,
        event_type="payment_received",
        channel="email"
    )

    # 1b. Dispatch Outbound Webhook to Developers
    try:
        await WebhookService.dispatch_event(
            db=db,
            org_id=sale.organization_id,
            event_name="payment.succeeded",
            payload={
                "sale_id": sale.id,
                "order_number": sale.order_number,
                "amount": sale.amount,
                "payment_status": sale.payment_status,
                "client_name": sale.client.account_name if sale.client else None,
            }
        )
    except Exception as wh_err:
        logger.warning(f"Failed to dispatch payment.succeeded webhook: {wh_err}")

    auto_fulfilled = False
    po_data = None

    # 2. Trigger Autonomous Fulfillment if enabled and not already fulfilled
    if sale.auto_fulfill_on_payment and not sale.purchase_orders:
        dest_address = None
        if sale.client and sale.client.company and sale.client.company.address:
            dest_address = sale.client.company.address
        elif sale.client:
            dest_address = f"{sale.client.account_name} Facility, Dock 1"

        agent = OrderFillerAgent()
        po_res = await agent.auto_fill_order(
            db=db,
            org_id=sale.organization_id,
            prompt=sale.items_summary,
            max_budget_limit=max(sale.amount * 1.5, 2000.0),
            client_sale_id=sale.id,
            destination_type="customer_dropship",
            destination_address=dest_address
        )
        auto_fulfilled = True
        po_data = {
            "po_number": po_res.get("po_number"),
            "carrier": po_res.get("carrier"),
            "tracking_number": po_res.get("tracking_number"),
            "total_cost": po_res.get("total_cost"),
            "status": po_res.get("status")
        }

        # 3. Dispatch Shipment Notification
        await NotificationService.create_and_send_notification(
            db=db,
            sale=sale,
            event_type="dispatched",
            channel="email",
            carrier=po_res.get("carrier"),
            tracking_number=po_res.get("tracking_number")
        )

    return {
        "success": True,
        "message": f"Payment recorded for Order {sale.order_number}. Fulfillment triggered: {auto_fulfilled}",
        "sale_id": sale.id,
        "order_number": sale.order_number,
        "payment_status": sale.payment_status,
        "auto_fulfilled": auto_fulfilled,
        "auto_fulfillment_triggered": auto_fulfilled,
        "purchase_order": po_data,
        "purchase_order_id": po_res.get("purchase_order_id") if (auto_fulfilled and po_res) else None
    }

@router.post("/payments/stripe/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Public webhook receiver for Stripe checkout events.
    Automatically marks sale as paid and triggers autonomous dropship order filler.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    event_type = body.get("type", "checkout.session.completed")
    data_object = body.get("data", {}).get("object", {})

    sale_id = data_object.get("client_reference_id") or data_object.get("metadata", {}).get("sale_id")
    session_id = data_object.get("id")

    if not sale_id and not session_id:
        return {"received": True, "message": "Ignored - no sale identifier found"}

    stmt = select(ClientSale).options(
        selectinload(ClientSale.client).selectinload(ClientAccount.company),
        selectinload(ClientSale.purchase_orders)
    )
    if sale_id:
        stmt = stmt.where(ClientSale.id == sale_id)
    else:
        stmt = stmt.where(ClientSale.stripe_session_id == session_id)

    result = await db.execute(stmt)
    sale = result.scalar_one_or_none()

    if not sale:
        return {"received": True, "message": "Sale record not found"}

    if event_type in ("checkout.session.completed", "invoice.payment_succeeded", "charge.succeeded"):
        sale.payment_status = "paid"
        await ReplenishmentService.advance_client_cadence_on_payment(db=db, sale=sale)
        payment_intent = data_object.get("payment_intent")
        if payment_intent:
            sale.stripe_payment_intent_id = payment_intent
        await db.commit()
        await db.refresh(sale)

        # Notify payment received
        await NotificationService.create_and_send_notification(
            db=db,
            sale=sale,
            event_type="payment_received",
            channel="email"
        )

        # Dispatch Outbound Webhook to Developers
        try:
            await WebhookService.dispatch_event(
                db=db,
                org_id=sale.organization_id,
                event_name="payment.succeeded",
                payload={
                    "sale_id": sale.id,
                    "order_number": sale.order_number,
                    "amount": sale.amount,
                    "payment_status": sale.payment_status,
                    "client_name": sale.client.account_name if sale.client else None,
                }
            )
        except Exception as wh_err:
            logger.warning(f"Failed to dispatch payment.succeeded webhook: {wh_err}")

        # Auto-fulfill dropship order
        if sale.auto_fulfill_on_payment and not sale.purchase_orders:
            dest_address = None
            if sale.client and sale.client.company and sale.client.company.address:
                dest_address = sale.client.company.address
            elif sale.client:
                dest_address = f"{sale.client.account_name} Facility, Dock 1"

            agent = OrderFillerAgent()
            po_res = await agent.auto_fill_order(
                db=db,
                org_id=sale.organization_id,
                prompt=sale.items_summary,
                max_budget_limit=max(sale.amount * 1.5, 2000.0),
                client_sale_id=sale.id,
                destination_type="customer_dropship",
                destination_address=dest_address
            )

            # Notify dispatched
            await NotificationService.create_and_send_notification(
                db=db,
                sale=sale,
                event_type="dispatched",
                channel="email",
                carrier=po_res.get("carrier"),
                tracking_number=po_res.get("tracking_number")
            )

    return {"received": True, "sale_id": sale.id, "payment_status": sale.payment_status}

@router.get("/public/checkout/{session_id}")
async def get_checkout_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ClientSale)
        .options(selectinload(ClientSale.client))
        .where(ClientSale.stripe_session_id == session_id)
    )
    res = await db.execute(stmt)
    sale = res.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=404, detail="Checkout session not found")

    org_stmt = select(Organization).where(Organization.id == sale.organization_id)
    org_res = await db.execute(org_stmt)
    org = org_res.scalar_one_or_none()
    org_name = (org.brand_name or org.name) if org else "Supplier"

    return {
        "session_id": session_id,
        "order_number": sale.order_number,
        "amount": sale.amount,
        "items_summary": sale.items_summary,
        "client_name": sale.client.account_name if sale.client else "Client",
        "organization_name": org_name,
        "brand_name": org_name,
        "brand_logo_url": org.brand_logo_url if org else None,
        "brand_accent_color": (org.brand_accent_color or "#4f46e5") if org else "#4f46e5",
        "support_email": (org.support_email or "support@therealbonz.com") if org else "support@therealbonz.com",
        "support_phone": org.support_phone if org else None,
        "custom_footer_text": org.custom_footer_text if org else None,
        "payment_status": sale.payment_status
    }
