import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.models.tenant import Organization
from app.models.crm import ClientAccount, ClientSale, CustomerNotification
from app.services.notification_service import NotificationService
from app.services.stripe_recurring_service import StripeRecurringService
from app.services.order_filler.agent import OrderFillerAgent

logger = logging.getLogger(__name__)

class ReplenishmentService:
    """
    Autonomous Re-Ordering & Client Replenishment Engine.
    Monitors client restock cadences, predicts reorder dates, drafts replenishment
    proposals with pre-filled Stripe checkout links, and automatically hands off
    to the AI Order Bot upon payment confirmation.
    """

    @staticmethod
    async def find_due_replenishments(
        db: AsyncSession,
        org_id: str,
        threshold_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Scans all active clients and returns those whose next_reorder_date
        falls within the threshold window (or is already overdue).
        """
        now = datetime.now(timezone.utc)
        target_cutoff = now + timedelta(days=threshold_days)

        stmt = (
            select(ClientAccount)
            .options(
                selectinload(ClientAccount.primary_contact),
                selectinload(ClientAccount.sales)
            )
            .where(
                ClientAccount.organization_id == org_id,
                ClientAccount.status == "active"
            )
            .order_by(ClientAccount.next_reorder_date.asc().nullslast())
        )
        result = await db.execute(stmt)
        clients = result.scalars().all()

        due_list = []
        for c in clients:
            reorder_date = c.next_reorder_date
            # If client has no next_reorder_date set yet, default from contract_start or now
            if not reorder_date:
                reorder_date = (c.contract_start_date or now) + timedelta(days=c.reorder_cadence_days or 30)
                c.next_reorder_date = reorder_date
                await db.flush()

            # Ensure timezone awareness for comparison
            if reorder_date.tzinfo is None:
                reorder_date = reorder_date.replace(tzinfo=timezone.utc)

            days_diff = (reorder_date.date() - now.date()).days

            # Include if overdue or due within threshold
            if days_diff <= threshold_days:
                urgency = "overdue" if days_diff < 0 else ("due_today" if days_diff == 0 else "due_soon")
                
                # Check if there is already an open replenishment proposal
                pending_sale = None
                for s in (c.sales or []):
                    if s.status in ("replenishment_pending", "pending", "invoiced") and s.payment_status == "unpaid":
                        pending_sale = {
                            "sale_id": s.id,
                            "order_number": s.order_number,
                            "amount": s.amount,
                            "items_summary": s.items_summary,
                            "stripe_checkout_url": s.stripe_checkout_url,
                            "created_at": s.created_at.isoformat() if s.created_at else None
                        }
                        break

                due_list.append({
                    "client_id": c.id,
                    "account_name": c.account_name,
                    "account_tier": c.account_tier,
                    "reorder_cadence_days": c.reorder_cadence_days,
                    "next_reorder_date": reorder_date.isoformat(),
                    "days_remaining": days_diff,
                    "urgency": urgency,
                    "contact_name": f"{c.primary_contact.first_name} {c.primary_contact.last_name}" if c.primary_contact else "Purchasing Lead",
                    "contact_email": c.primary_contact.email if c.primary_contact else None,
                    "contact_phone": c.primary_contact.phone if c.primary_contact else None,
                    "total_revenue": c.total_revenue,
                    "order_count": c.order_count,
                    "has_payment_method_on_file": bool(c.has_payment_method_on_file),
                    "auto_charge_enabled": bool(c.auto_charge_enabled),
                    "card_brand": c.card_brand,
                    "card_last4": c.card_last4,
                    "auto_charge_limit": c.auto_charge_limit,
                    "pending_replenishment": pending_sale
                })

        return due_list

    @staticmethod
    async def generate_replenishment_proposal(
        db: AsyncSession,
        org_id: str,
        client_id: str,
        custom_items: Optional[str] = None,
        custom_amount: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Creates an intelligent replenishment sales proposal for a client, generates
        a hosted Stripe checkout payment link, and records the outbound proposal notification.
        """
        stmt = (
            select(ClientAccount)
            .options(
                selectinload(ClientAccount.primary_contact),
                selectinload(ClientAccount.company),
                selectinload(ClientAccount.sales)
            )
            .where(
                ClientAccount.id == client_id,
                ClientAccount.organization_id == org_id
            )
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()
        if not client:
            raise ValueError(f"Client account {client_id} not found")

        org_stmt = select(Organization).where(Organization.id == org_id)
        org_res = await db.execute(org_stmt)
        org = org_res.scalar_one_or_none()

        # Check if an unpaid replenishment sale already exists
        for existing in (client.sales or []):
            if existing.status == "replenishment_pending" and existing.payment_status == "unpaid":
                # Check if client has card-on-file auto-charge eligible
                if client.has_payment_method_on_file and client.auto_charge_enabled:
                    if client.auto_charge_limit is None or existing.amount <= client.auto_charge_limit:
                        charge_res = await StripeRecurringService.charge_stored_payment_method(
                            db=db,
                            client=client,
                            sale=existing,
                            org=org
                        )
                        if charge_res.get("success"):
                            await ReplenishmentService.advance_client_cadence_on_payment(db=db, sale=existing)
                            await db.commit()

                            try:
                                await NotificationService.create_and_send_notification(
                                    db=db,
                                    sale=existing,
                                    event_type="payment_received",
                                    channel="email"
                                )
                            except Exception as e:
                                logger.warning(f"Could not dispatch payment confirmation: {e}")

                            if existing.auto_fulfill_on_payment:
                                try:
                                    dest_address = client.company.address if (client.company and client.company.address) else f"{client.account_name} Facility"
                                    agent = OrderFillerAgent()
                                    await agent.auto_fill_order(
                                        db=db,
                                        org_id=org_id,
                                        prompt=existing.items_summary,
                                        max_budget_limit=max(existing.amount * 1.5, 2000.0),
                                        client_sale_id=existing.id,
                                        destination_type="customer_dropship",
                                        destination_address=dest_address
                                    )
                                    await NotificationService.create_and_send_notification(
                                        db=db,
                                        sale=existing,
                                        event_type="order_shipped",
                                        channel="email"
                                    )
                                except Exception as e:
                                    logger.error(f"Auto-charge fulfillment error: {e}")

                            return {
                                "client_id": client.id,
                                "sale_id": existing.id,
                                "order_number": existing.order_number,
                                "amount": existing.amount,
                                "items_summary": existing.items_summary,
                                "checkout_url": existing.stripe_checkout_url,
                                "auto_charged": True,
                                "charge_info": charge_res,
                                "is_new": False
                            }

                logger.info(f"Re-using existing pending replenishment sale {existing.order_number} for client {client.account_name}")
                return {
                    "client_id": client.id,
                    "sale_id": existing.id,
                    "order_number": existing.order_number,
                    "amount": existing.amount,
                    "items_summary": existing.items_summary,
                    "checkout_url": existing.stripe_checkout_url,
                    "auto_charged": False,
                    "is_new": False
                }

        now = datetime.now(timezone.utc)
        
        # Determine items and amount from past sales history or defaults
        items_summary = custom_items
        amount = custom_amount

        if not items_summary or not amount:
            completed_sales = [s for s in (client.sales or []) if s.status not in ("cancelled", "replenishment_pending")]
            if completed_sales:
                last_sale = completed_sales[0]
                if not items_summary:
                    items_summary = f"[Cadence Restock] {last_sale.items_summary}"
                if not amount:
                    amount = last_sale.amount
            else:
                if not items_summary:
                    items_summary = f"[Scheduled Restock] Standard Operational Inventory Replenishment ({client.reorder_cadence_days} Day Cadence)"
                if not amount:
                    amount = 850.00

        order_number = f"REP-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
        session_id = f"cs_test_rep_{uuid.uuid4().hex[:16]}"
        checkout_url = f"/checkout/pay/{session_id}"

        customer_email = client.primary_contact.email if client.primary_contact else None
        customer_phone = client.primary_contact.phone if client.primary_contact else None

        sale = ClientSale(
            organization_id=org_id,
            client_id=client.id,
            order_number=order_number,
            amount=amount,
            sale_date=now,
            status="replenishment_pending",
            payment_method="stripe",
            payment_status="unpaid",
            stripe_session_id=session_id,
            stripe_checkout_url=checkout_url,
            auto_fulfill_on_payment=True,
            customer_email=customer_email,
            customer_phone=customer_phone,
            items_summary=items_summary,
            sales_rep_name="AI Replenishment Engine",
            notes=f"Autonomous replenishment generated based on {client.reorder_cadence_days}-day restock cadence."
        )
        db.add(sale)
        await db.flush()

        auto_charged = False
        charge_info = None

        # Check if stored card-on-file auto-charge should be processed immediately
        if client.has_payment_method_on_file and client.auto_charge_enabled:
            if client.auto_charge_limit is None or sale.amount <= client.auto_charge_limit:
                charge_res = await StripeRecurringService.charge_stored_payment_method(
                    db=db,
                    client=client,
                    sale=sale,
                    org=org
                )
                if charge_res.get("success"):
                    auto_charged = True
                    charge_info = charge_res
                    await ReplenishmentService.advance_client_cadence_on_payment(db=db, sale=sale)
                    await db.commit()

                    try:
                        await NotificationService.create_and_send_notification(
                            db=db,
                            sale=sale,
                            event_type="payment_received",
                            channel="email"
                        )
                    except Exception as e:
                        logger.warning(f"Could not dispatch payment confirmation: {e}")

                    # Autonomous fulfillment
                    if sale.auto_fulfill_on_payment:
                        try:
                            dest_address = client.company.address if (client.company and client.company.address) else f"{client.account_name} Facility"
                            agent = OrderFillerAgent()
                            await agent.auto_fill_order(
                                db=db,
                                org_id=org_id,
                                prompt=sale.items_summary,
                                max_budget_limit=max(sale.amount * 1.5, 2000.0),
                                client_sale_id=sale.id,
                                destination_type="customer_dropship",
                                destination_address=dest_address
                            )
                            await NotificationService.create_and_send_notification(
                                db=db,
                                sale=sale,
                                event_type="order_shipped",
                                channel="email"
                            )
                        except Exception as e:
                            logger.error(f"Auto-charge fulfillment error: {e}")

        # If not auto-charged, dispatch replenishment proposal notification
        notification_id = None
        if not auto_charged:
            contact_name = client.primary_contact.first_name if client.primary_contact else "Procurement Manager"
            notification_body = (
                f"Hello {contact_name}, your {client.reorder_cadence_days}-day replenishment schedule for {client.account_name} "
                f"is due. We have prepared Order #{order_number} ({items_summary}) for ${amount:.2f}. "
                f"Pay invoice online to trigger immediate autonomous dispatch: https://therealbonz.com/JsProject{checkout_url}"
            )

            notification = CustomerNotification(
                organization_id=org_id,
                client_sale_id=sale.id,
                recipient=customer_email or "client@example.com",
                channel="email",
                event_type="replenishment_proposal",
                title=f"Scheduled Restock Proposal: Order #{order_number}",
                message_body=notification_body,
                tracking_url=f"https://therealbonz.com/JsProject/track/{order_number}",
                status="sent"
            )
            db.add(notification)
            await db.commit()
            notification_id = notification.id

        await db.refresh(sale)

        return {
            "client_id": client.id,
            "sale_id": sale.id,
            "order_number": sale.order_number,
            "amount": sale.amount,
            "items_summary": sale.items_summary,
            "checkout_url": sale.stripe_checkout_url,
            "notification_id": notification_id,
            "auto_charged": auto_charged,
            "charge_info": charge_info,
            "is_new": True
        }

    @staticmethod
    async def snooze_replenishment(
        db: AsyncSession,
        org_id: str,
        client_id: str,
        snooze_days: int = 14
    ) -> Dict[str, Any]:
        """
        Pushes the client's next_reorder_date forward by snooze_days.
        """
        stmt = (
            select(ClientAccount)
            .where(
                ClientAccount.id == client_id,
                ClientAccount.organization_id == org_id
            )
        )
        result = await db.execute(stmt)
        client = result.scalar_one_or_none()
        if not client:
            raise ValueError("Client account not found")

        now = datetime.now(timezone.utc)
        base_date = client.next_reorder_date or now
        if base_date.tzinfo is None:
            base_date = base_date.replace(tzinfo=timezone.utc)
        if base_date < now:
            base_date = now

        client.next_reorder_date = base_date + timedelta(days=snooze_days)
        await db.commit()
        await db.refresh(client)

        return {
            "client_id": client.id,
            "account_name": client.account_name,
            "new_reorder_date": client.next_reorder_date.isoformat(),
            "snoozed_days": snooze_days
        }

    @staticmethod
    async def advance_client_cadence_on_payment(
        db: AsyncSession,
        sale: ClientSale
    ):
        """
        Advances the client's next_reorder_date by their cadence days whenever a sale is completed/paid.
        """
        if not sale.client_id:
            return

        stmt = select(ClientAccount).where(ClientAccount.id == sale.client_id)
        res = await db.execute(stmt)
        client = res.scalar_one_or_none()
        if client:
            cadence = client.reorder_cadence_days or 30
            client.next_reorder_date = datetime.now(timezone.utc) + timedelta(days=cadence)
            # If the sale was a replenishment proposal, update status to completed
            if sale.status == "replenishment_pending":
                sale.status = "completed"
            await db.flush()
