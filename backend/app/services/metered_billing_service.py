from datetime import datetime, timezone, timedelta
import logging
import uuid
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.models.tenant import Organization, User
from app.models.crm import ClientAccount, ClientSale, SaaSLicense
from app.models.metered_billing import MeteredUsageRecord, MeteredBillingInvoice
from app.models.hitl import AuditLog
from app.services.stripe_recurring_service import StripeRecurringService
from app.services.webhook_service import WebhookService
from app.schemas.metered_billing import (
    MetricAllowanceDetail,
    MeteredBillingSummaryResponse,
    MetricCatalogItem
)

logger = logging.getLogger(__name__)

METRIC_CATALOG: Dict[str, Dict[str, Any]] = {
    "api_calls": {
        "display_name": "REST API Calls",
        "unit_label": "calls",
        "description": "Programmatic developer API and webhooks requests",
        "allowances": {
            "starter": 25000.0,
            "pro": 100000.0,
            "enterprise": 1000000.0,
            "custom": 200000.0,
        },
        "overage_rates": {
            "starter": 0.002,    # $2.00 / 1k
            "pro": 0.0015,      # $1.50 / 1k
            "enterprise": 0.001, # $1.00 / 1k
            "custom": 0.0015,
        }
    },
    "ai_agent_runs": {
        "display_name": "Autonomous AI Agent Runs",
        "unit_label": "runs",
        "description": "Gemini AI lead qualification, outreach drafting & intent analysis",
        "allowances": {
            "starter": 100.0,
            "pro": 500.0,
            "enterprise": 5000.0,
            "custom": 1000.0,
        },
        "overage_rates": {
            "starter": 0.15,
            "pro": 0.10,
            "enterprise": 0.05,
            "custom": 0.10,
        }
    },
    "procurement_orders": {
        "display_name": "Autonomous Procurement POs",
        "unit_label": "orders",
        "description": "OrderFillerAgent supplier checkouts across Amazon, Grainger & DigiKey",
        "allowances": {
            "starter": 20.0,
            "pro": 100.0,
            "enterprise": 1000.0,
            "custom": 250.0,
        },
        "overage_rates": {
            "starter": 2.00,
            "pro": 1.50,
            "enterprise": 1.00,
            "custom": 1.50,
        }
    },
    "edi_transactions": {
        "display_name": "EDI 850/856 Supply Transactions",
        "unit_label": "transactions",
        "description": "Standardized electronic dropship supplier order & advance ship notices",
        "allowances": {
            "starter": 50.0,
            "pro": 250.0,
            "enterprise": 2500.0,
            "custom": 500.0,
        },
        "overage_rates": {
            "starter": 0.75,
            "pro": 0.50,
            "enterprise": 0.25,
            "custom": 0.50,
        }
    },
    "storage_mb": {
        "display_name": "Cloud Document & Telemetry Storage",
        "unit_label": "MB",
        "description": "Archived PDF invoices, QR packing slips, and demand forecast logs",
        "allowances": {
            "starter": 5000.0,
            "pro": 25000.0,
            "enterprise": 250000.0,
            "custom": 50000.0,
        },
        "overage_rates": {
            "starter": 0.02,
            "pro": 0.015,
            "enterprise": 0.01,
            "custom": 0.015,
        }
    }
}


class MeteredBillingService:
    @staticmethod
    def get_metric_catalog() -> List[MetricCatalogItem]:
        """Returns standard metric catalog with tier included units and overage pricing."""
        catalog = []
        for key, info in METRIC_CATALOG.items():
            allowances = info["allowances"]
            rates = info["overage_rates"]
            catalog.append(
                MetricCatalogItem(
                    metric_name=key,
                    display_name=info["display_name"],
                    unit_label=info["unit_label"],
                    description=info["description"],
                    starter_included=allowances.get("starter", 0.0),
                    pro_included=allowances.get("pro", 0.0),
                    enterprise_included=allowances.get("enterprise", 0.0),
                    starter_rate=rates.get("starter", 0.0),
                    pro_rate=rates.get("pro", 0.0),
                    enterprise_rate=rates.get("enterprise", 0.0),
                )
            )
        return catalog

    @staticmethod
    async def record_usage(
        db: AsyncSession,
        org_id: str,
        license_id: str,
        metric_name: str,
        quantity: float = 1.0,
        idempotency_key: Optional[str] = None,
        source: str = "api_gateway",
        metadata: Optional[Dict[str, Any]] = None
    ) -> MeteredUsageRecord:
        """
        Records a metered consumption event.
        Guarantees deduplication if idempotency_key is present.
        """
        # Fetch license
        stmt = select(SaaSLicense).where(
            SaaSLicense.id == license_id,
            SaaSLicense.organization_id == org_id
        )
        res = await db.execute(stmt)
        lic = res.scalar_one_or_none()
        if not lic:
            raise ValueError(f"SaaSLicense '{license_id}' not found in this organization")

        # Idempotency check
        if idempotency_key:
            idem_stmt = select(MeteredUsageRecord).where(
                MeteredUsageRecord.organization_id == org_id,
                MeteredUsageRecord.license_id == license_id,
                MeteredUsageRecord.metric_name == metric_name,
                MeteredUsageRecord.idempotency_key == idempotency_key
            )
            idem_res = await db.execute(idem_stmt)
            existing = idem_res.scalar_one_or_none()
            if existing:
                logger.info(f"[METERED BILLING] Idempotent hit for key {idempotency_key} on license {license_id}")
                return existing

        now = datetime.now(timezone.utc)
        record = MeteredUsageRecord(
            organization_id=org_id,
            client_id=lic.client_id,
            license_id=lic.id,
            metric_name=metric_name,
            quantity=float(quantity),
            idempotency_key=idempotency_key,
            source=source,
            billing_cycle_id=None,
            recorded_at=now,
            metadata_json=metadata or {}
        )
        db.add(record)

        # Update license telemetry timestamp & API quota if applicable
        lic.last_telemetry_at = now
        if metric_name == "api_calls":
            lic.current_quota_used = int((lic.current_quota_used or 0) + quantity)

        await db.commit()
        await db.refresh(record)
        return record

    @staticmethod
    async def batch_record_usage(
        db: AsyncSession,
        org_id: str,
        license_id: str,
        events: List[Dict[str, Any]]
    ) -> List[MeteredUsageRecord]:
        """Ingests multiple usage records in a single database transaction."""
        stmt = select(SaaSLicense).where(
            SaaSLicense.id == license_id,
            SaaSLicense.organization_id == org_id
        )
        res = await db.execute(stmt)
        lic = res.scalar_one_or_none()
        if not lic:
            raise ValueError(f"SaaSLicense '{license_id}' not found in this organization")

        now = datetime.now(timezone.utc)
        results = []
        for ev in events:
            metric = ev.get("metric_name", "api_calls")
            qty = float(ev.get("quantity", 1.0))
            idem_key = ev.get("idempotency_key")
            src = ev.get("source", "api_gateway")
            meta = ev.get("metadata", {})

            if idem_key:
                idem_stmt = select(MeteredUsageRecord).where(
                    MeteredUsageRecord.organization_id == org_id,
                    MeteredUsageRecord.license_id == license_id,
                    MeteredUsageRecord.metric_name == metric,
                    MeteredUsageRecord.idempotency_key == idem_key
                )
                idem_res = await db.execute(idem_stmt)
                existing = idem_res.scalar_one_or_none()
                if existing:
                    results.append(existing)
                    continue

            rec = MeteredUsageRecord(
                organization_id=org_id,
                client_id=lic.client_id,
                license_id=lic.id,
                metric_name=metric,
                quantity=qty,
                idempotency_key=idem_key,
                source=src,
                billing_cycle_id=None,
                recorded_at=now,
                metadata_json=meta
            )
            db.add(rec)
            results.append(rec)
            if metric == "api_calls":
                lic.current_quota_used = int((lic.current_quota_used or 0) + qty)

        lic.last_telemetry_at = now
        await db.commit()
        for r in results:
            await db.refresh(r)
        return results

    @staticmethod
    async def get_meter_summary(
        db: AsyncSession,
        license_id: str,
        org_id: str
    ) -> MeteredBillingSummaryResponse:
        """
        Calculates real-time consumption vs included tier allowances and accrued overage fees.
        """
        stmt = select(SaaSLicense).options(
            selectinload(SaaSLicense.client)
        ).where(
            SaaSLicense.id == license_id,
            SaaSLicense.organization_id == org_id
        )
        res = await db.execute(stmt)
        lic = res.scalar_one_or_none()
        if not lic:
            raise ValueError(f"SaaSLicense '{license_id}' not found")

        client_name = lic.client.account_name if lic.client else "Client Account"
        tier = (lic.plan_tier or "pro").lower()

        # Determine billing cycle window
        now = datetime.now(timezone.utc)
        inv_stmt = select(MeteredBillingInvoice).where(
            MeteredBillingInvoice.license_id == license_id,
            MeteredBillingInvoice.organization_id == org_id
        ).order_by(desc(MeteredBillingInvoice.cycle_end))
        inv_res = await db.execute(inv_stmt)
        last_inv = inv_res.scalars().first()

        if last_inv and last_inv.cycle_end:
            c_start = last_inv.cycle_end
            if c_start.tzinfo is None:
                c_start = c_start.replace(tzinfo=timezone.utc)
        else:
            c_start = lic.contract_start_date or (now - timedelta(days=30))
            if c_start.tzinfo is None:
                c_start = c_start.replace(tzinfo=timezone.utc)

        c_end = c_start + timedelta(days=30)
        days_left = max(0, (c_end - now).days)

        # Aggregate unbilled usage for this license
        usage_stmt = select(
            MeteredUsageRecord.metric_name,
            func.sum(MeteredUsageRecord.quantity).label("total_quantity")
        ).where(
            MeteredUsageRecord.license_id == license_id,
            MeteredUsageRecord.organization_id == org_id,
            MeteredUsageRecord.billing_cycle_id == None
        ).group_by(MeteredUsageRecord.metric_name)

        usage_res = await db.execute(usage_stmt)
        consumed_map = {row[0]: float(row[1] or 0.0) for row in usage_res.all()}

        metrics_list = []
        total_accrued = 0.0

        for m_key, m_info in METRIC_CATALOG.items():
            included = m_info["allowances"].get(tier, m_info["allowances"].get("pro", 100.0))
            rate = m_info["overage_rates"].get(tier, m_info["overage_rates"].get("pro", 0.05))

            # If license has custom monthly_quota_units on api_calls, honor it
            if m_key == "api_calls" and lic.monthly_quota_units and lic.monthly_quota_units > 0:
                included = float(lic.monthly_quota_units)

            consumed = consumed_map.get(m_key, 0.0)
            overage = max(0.0, consumed - included)
            accrued = round(overage * rate, 2)
            total_accrued += accrued
            util_pct = round((consumed / included * 100.0) if included > 0 else 0.0, 1)

            metrics_list.append(
                MetricAllowanceDetail(
                    metric_name=m_key,
                    display_name=m_info["display_name"],
                    unit_label=m_info["unit_label"],
                    included_units=included,
                    consumed_units=consumed,
                    overage_units=overage,
                    unit_overage_rate=rate,
                    accrued_charge=accrued,
                    utilization_pct=util_pct
                )
            )

        # Project cycle overage based on run-rate
        cycle_total_days = 30
        elapsed_days = max(1, min(cycle_total_days, (now - c_start).days or 1))
        projected = round(total_accrued * (cycle_total_days / elapsed_days), 2)

        return MeteredBillingSummaryResponse(
            license_id=lic.id,
            license_key=lic.license_key,
            client_id=lic.client_id,
            client_name=client_name,
            plan_tier=lic.plan_tier,
            cycle_start=c_start,
            cycle_end=c_end,
            days_remaining_in_cycle=days_left,
            metrics=metrics_list,
            total_accrued_overage=round(total_accrued, 2),
            projected_cycle_overage=projected
        )

    @staticmethod
    async def settle_billing_cycle(
        db: AsyncSession,
        license_id: str,
        org: Organization,
        user: Optional[User] = None,
        auto_charge: bool = True,
        notes: Optional[str] = None
    ) -> MeteredBillingInvoice:
        """
        Closes and settles the current metered billing cycle:
        - Calculates total overages across metrics
        - Creates a MeteredBillingInvoice
        - Creates a synchronized ClientSale
        - Automatically charges stored card on file if authorized
        - Dispatches developer outbound webhooks
        - Logs audit record
        """
        stmt = select(SaaSLicense).options(
            selectinload(SaaSLicense.client).selectinload(ClientAccount.primary_contact)
        ).where(
            SaaSLicense.id == license_id,
            SaaSLicense.organization_id == org.id
        )
        res = await db.execute(stmt)
        lic = res.scalar_one_or_none()
        if not lic:
            raise ValueError(f"SaaSLicense '{license_id}' not found")

        client = lic.client
        if not client:
            raise ValueError("Associated ClientAccount not found for license")

        # Get summary
        summary = await MeteredBillingService.get_meter_summary(db, license_id, org.id)
        now = datetime.now(timezone.utc)
        inv_number = f"INV-METER-{now.strftime('%Y%m')}-{uuid.uuid4().hex[:6].upper()}"

        line_items = []
        for m in summary.metrics:
            line_items.append({
                "metric_name": m.metric_name,
                "display_name": m.display_name,
                "unit_label": m.unit_label,
                "included_units": m.included_units,
                "consumed_units": m.consumed_units,
                "overage_units": m.overage_units,
                "unit_overage_rate": m.unit_overage_rate,
                "subtotal": m.accrued_charge
            })

        subtotal = round(summary.total_accrued_overage, 2)
        tax = 0.0
        total = round(subtotal + tax, 2)

        client_sale = None
        payment_status = "paid" if total == 0.0 else "unpaid"
        payment_method = "card_on_file" if (client.has_payment_method_on_file and client.auto_charge_enabled) else "credit_terms_30"
        stripe_payment_intent = None

        if total > 0.0:
            order_num = f"SO-OVERAGE-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
            active_lines = [f"{item['display_name']}: {item['overage_units']:,.0f} overage (${item['subtotal']:.2f})" for item in line_items if item['overage_units'] > 0]
            summary_desc = " | ".join(active_lines) if active_lines else f"Metered Billing Overages for {lic.license_key}"

            client_sale = ClientSale(
                organization_id=org.id,
                client_id=client.id,
                order_number=order_num,
                amount=total,
                sale_date=now,
                status="completed",
                payment_method=payment_method,
                payment_status=payment_status,
                auto_fulfill_on_payment=False,
                items_summary=f"Metered Consumption Overages: {summary_desc}",
                sales_rep_name="Autonomous Metered Billing Engine",
                notes=f"Auto-generated for license {lic.license_key} overage settlement ({summary.cycle_start.strftime('%b %d')} - {summary.cycle_end.strftime('%b %d')})"
            )
            db.add(client_sale)
            await db.flush()

            # Attempt auto-charge if enabled
            if auto_charge and client.has_payment_method_on_file and client.auto_charge_enabled:
                charge_res = await StripeRecurringService.charge_stored_payment_method(
                    db=db,
                    client=client,
                    sale=client_sale,
                    org=org
                )
                if charge_res.get("success"):
                    payment_status = "paid"
                    client_sale.payment_status = "paid"
                    stripe_payment_intent = charge_res.get("payment_intent_id") or f"pi_sim_{uuid.uuid4().hex[:16]}"
                else:
                    logger.warning(f"[METERED BILLING] Auto-charge failed: {charge_res.get('error')}")
                    payment_status = "unpaid"

        invoice = MeteredBillingInvoice(
            organization_id=org.id,
            client_id=client.id,
            license_id=lic.id,
            invoice_number=inv_number,
            cycle_start=summary.cycle_start,
            cycle_end=summary.cycle_end,
            status="settled",
            line_items=line_items,
            subtotal_overage_amount=subtotal,
            tax_amount=tax,
            total_billed_amount=total,
            client_sale_id=client_sale.id if client_sale else None,
            payment_method=payment_method,
            payment_status=payment_status,
            stripe_payment_intent_id=stripe_payment_intent,
            settled_at=now,
            notes=notes or f"Settled {len(line_items)} metered metrics (Total Overages: ${total:.2f})"
        )
        db.add(invoice)
        await db.flush()

        # Link all unbilled usage records to this invoice
        unbilled_stmt = select(MeteredUsageRecord).where(
            MeteredUsageRecord.license_id == license_id,
            MeteredUsageRecord.organization_id == org.id,
            MeteredUsageRecord.billing_cycle_id == None
        )
        unbilled_res = await db.execute(unbilled_stmt)
        unbilled_records = unbilled_res.scalars().all()
        for r in unbilled_records:
            r.billing_cycle_id = invoice.id

        # Audit log
        audit = AuditLog(
            organization_id=org.id,
            actor_type="system" if not user else "human_rep",
            actor_id=user.id if user else "metered_billing_engine",
            action="metered_billing_settled",
            target_entity="metered_billing_invoice",
            target_id=invoice.id,
            payload={
                "invoice_number": inv_number,
                "license_id": lic.id,
                "client_id": client.id,
                "total_billed": total,
                "payment_status": payment_status,
                "records_settled_count": len(unbilled_records)
            }
        )
        db.add(audit)

        # Dispatch developer webhooks
        try:
            if total > 0.0:
                await WebhookService.dispatch_event(
                    org_id=org.id,
                    event_type="order.created",
                    data={
                        "order_number": client_sale.order_number,
                        "amount": total,
                        "client_id": client.id,
                        "type": "metered_overage_invoice",
                        "invoice_number": inv_number
                    },
                    db=db
                )
                if payment_status == "paid":
                    await WebhookService.dispatch_event(
                        org_id=org.id,
                        event_type="payment.succeeded",
                        data={
                            "order_number": client_sale.order_number,
                            "amount": total,
                            "payment_method": payment_method,
                            "invoice_number": inv_number,
                            "transaction_id": stripe_payment_intent
                        },
                        db=db
                    )
        except Exception as e:
            logger.warning(f"[METERED BILLING] Webhook dispatch warning: {e}")

        await db.commit()
        inv_stmt = select(MeteredBillingInvoice).options(
            selectinload(MeteredBillingInvoice.client)
        ).where(MeteredBillingInvoice.id == invoice.id)
        refreshed = (await db.execute(inv_stmt)).scalar_one()
        return refreshed

    @staticmethod
    async def list_invoices(
        db: AsyncSession,
        org_id: str,
        license_id: Optional[str] = None
    ) -> List[MeteredBillingInvoice]:
        """Lists historical metered billing invoices."""
        stmt = select(MeteredBillingInvoice).options(
            selectinload(MeteredBillingInvoice.client)
        ).where(MeteredBillingInvoice.organization_id == org_id)

        if license_id:
            stmt = stmt.where(MeteredBillingInvoice.license_id == license_id)

        stmt = stmt.order_by(desc(MeteredBillingInvoice.settled_at))
        res = await db.execute(stmt)
        return res.scalars().all()

    @staticmethod
    async def get_invoice(
        db: AsyncSession,
        invoice_id: str,
        org_id: str
    ) -> Optional[MeteredBillingInvoice]:
        """Retrieves a single metered billing invoice."""
        stmt = select(MeteredBillingInvoice).options(
            selectinload(MeteredBillingInvoice.client)
        ).where(
            MeteredBillingInvoice.id == invoice_id,
            MeteredBillingInvoice.organization_id == org_id
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()
