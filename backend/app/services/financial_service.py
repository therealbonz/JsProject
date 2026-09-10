import csv
import io
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.models.tenant import Organization, OrganizationMembership, User
from app.models.crm import ClientAccount, ClientSale, SaaSLicense, SaaSExpansionProposal
from app.models.procurement import PurchaseOrder, Supplier
from app.schemas.financials import (
    ExecutiveOverviewResponse,
    FinancialReconciliationResponse,
    ReconciliationLineItem,
    RepCommissionSummary,
    RepCommissionLeaderboardResponse,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

class FinancialService:
    """
    Executive financial intelligence, reconciliation engine, and sales commission accounting.
    """

    @staticmethod
    def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    @staticmethod
    async def compute_executive_overview(tenant_id: str, db: AsyncSession) -> ExecutiveOverviewResponse:
        """
        Calculates executive KPIs: MRR, ARR, revenue collected, COGS, gross & net margins, commissions, and churn risk.
        """
        # 1. SaaS License MRR & Churn Risk
        lic_stmt = select(SaaSLicense).where(
            SaaSLicense.organization_id == tenant_id,
            SaaSLicense.license_status == "active"
        )
        lic_result = await db.execute(lic_stmt)
        licenses = lic_result.scalars().all()

        license_mrr = sum(l.mrr for l in licenses)
        at_risk_arr = sum(l.arr for l in licenses if l.churn_risk_level in ["at_risk", "critical"])

        # 2. Client Accounts & Replenishment Recurring Run-Rate
        acc_stmt = select(ClientAccount).where(
            ClientAccount.organization_id == tenant_id,
            ClientAccount.status == "active"
        )
        acc_result = await db.execute(acc_stmt)
        accounts = acc_result.scalars().all()
        active_accounts_count = len(accounts)

        # Projected monthly recurring revenue from automated card-on-file restock schedules
        replenish_mrr = 0.0
        for acc in accounts:
            if acc.auto_charge_enabled and acc.order_count > 0 and acc.reorder_cadence_days > 0:
                avg_order_value = acc.total_revenue / acc.order_count
                monthly_run_rate = avg_order_value * (30.0 / float(acc.reorder_cadence_days))
                replenish_mrr += monthly_run_rate

        total_mrr = round(license_mrr + replenish_mrr, 2)
        total_arr = round(total_mrr * 12.0, 2)
        arpu = round(total_mrr / max(1, active_accounts_count), 2) if active_accounts_count > 0 else 0.0

        # 3. Client Sales: Paid Revenue vs Invoiced Accounts Receivable
        sales_stmt = select(ClientSale).where(ClientSale.organization_id == tenant_id)
        sales_result = await db.execute(sales_stmt)
        sales = sales_result.scalars().all()

        total_collected_revenue = sum(s.amount for s in sales if s.payment_status == "paid")
        total_unpaid_invoiced = sum(s.amount for s in sales if s.payment_status == "unpaid" and s.status != "cancelled")

        # 4. Supplier POs: Cost of Goods Sold (COGS)
        po_stmt = select(PurchaseOrder).options(selectinload(PurchaseOrder.supplier)).where(
            PurchaseOrder.organization_id == tenant_id,
            PurchaseOrder.status.in_(["ordered", "shipped", "in_transit", "delivered", "auto_approved"])
        )
        po_result = await db.execute(po_stmt)
        pos = po_result.scalars().all()

        total_supplier_cogs = sum(po.total_cost for po in pos)

        # Group top supplier expenses
        supplier_spend_map: Dict[str, Dict[str, Any]] = {}
        for po in pos:
            sup_name = po.supplier.name if po.supplier else "Standard Supply Distributor"
            if sup_name not in supplier_spend_map:
                supplier_spend_map[sup_name] = {"supplier": sup_name, "total_spend": 0.0, "po_count": 0}
            supplier_spend_map[sup_name]["total_spend"] += po.total_cost
            supplier_spend_map[sup_name]["po_count"] += 1

        top_suppliers = sorted(
            supplier_spend_map.values(),
            key=lambda x: x["total_spend"],
            reverse=True
        )[:5]
        for sup in top_suppliers:
            sup["total_spend"] = round(sup["total_spend"], 2)

        # 5. Sales Commission Liabilities
        commissions_data = await FinancialService.compute_rep_commissions(tenant_id, db)
        total_commissions_earned = commissions_data.total_commissions_payable

        # 6. Margins
        gross_profit = round(total_collected_revenue - total_supplier_cogs, 2)
        gross_margin_pct = round((gross_profit / total_collected_revenue * 100.0), 1) if total_collected_revenue > 0 else 0.0

        net_settlement_margin = round(gross_profit - total_commissions_earned, 2)
        net_margin_pct = round((net_settlement_margin / total_collected_revenue * 100.0), 1) if total_collected_revenue > 0 else 0.0

        # 7. Net Revenue Retention (NRR) estimate
        exp_stmt = select(SaaSExpansionProposal).where(
            SaaSExpansionProposal.organization_id == tenant_id,
            SaaSExpansionProposal.status.in_(["approved", "accepted"])
        )
        exp_res = await db.execute(exp_stmt)
        expansions = exp_res.scalars().all()
        expansion_arr = sum(e.arr_delta for e in expansions)

        baseline_arr = max(1.0, total_arr)
        nrr_ratio = 100.0 + ((expansion_arr - at_risk_arr) / baseline_arr * 100.0)
        nrr_pct = round(max(75.0, min(150.0, nrr_ratio)), 1)

        return ExecutiveOverviewResponse(
            mrr=round(total_mrr, 2),
            arr=round(total_arr, 2),
            total_collected_revenue=round(total_collected_revenue, 2),
            total_unpaid_invoiced=round(total_unpaid_invoiced, 2),
            total_supplier_cogs=round(total_supplier_cogs, 2),
            gross_profit=gross_profit,
            gross_margin_pct=gross_margin_pct,
            total_commissions_earned=round(total_commissions_earned, 2),
            net_settlement_margin=net_settlement_margin,
            net_margin_pct=net_margin_pct,
            active_client_accounts=active_accounts_count,
            arpu=arpu,
            at_risk_arr=round(at_risk_arr, 2),
            nrr_pct=nrr_pct,
            top_supplier_expenses=top_suppliers,
            currency="USD"
        )

    @staticmethod
    async def generate_reconciliation_statement(
        tenant_id: str,
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> FinancialReconciliationResponse:
        """
        Generates structured multi-stream reconciliation ledger reconciling customer sales, supplier PO costs, and rep commissions.
        """
        now = datetime.now(timezone.utc)
        period_start = FinancialService._ensure_utc(start_date) or (now - timedelta(days=90))
        period_end = FinancialService._ensure_utc(end_date) or now

        # Fetch sales within period
        sales_stmt = select(ClientSale).options(selectinload(ClientSale.client)).where(
            ClientSale.organization_id == tenant_id,
            ClientSale.sale_date >= period_start,
            ClientSale.sale_date <= period_end
        ).order_by(desc(ClientSale.sale_date))
        sales_result = await db.execute(sales_stmt)
        sales = sales_result.scalars().all()

        # Fetch supplier POs within period
        po_stmt = select(PurchaseOrder).options(selectinload(PurchaseOrder.supplier)).where(
            PurchaseOrder.organization_id == tenant_id,
            PurchaseOrder.placed_at >= period_start,
            PurchaseOrder.placed_at <= period_end
        ).order_by(desc(PurchaseOrder.placed_at))
        po_result = await db.execute(po_stmt)
        pos = po_result.scalars().all()

        # Fetch rep commission rates map
        members_stmt = select(OrganizationMembership, User).join(
            User, User.id == OrganizationMembership.user_id
        ).where(OrganizationMembership.organization_id == tenant_id)
        members_res = await db.execute(members_stmt)
        members_rows = members_res.all()

        rep_rate_map: Dict[str, float] = {}
        for m, u in members_rows:
            rate = getattr(m, "commission_rate_pct", 10.0) or 10.0
            rep_rate_map[u.full_name.lower().strip()] = rate
            rep_rate_map[u.email.lower().strip()] = rate

        line_items: List[ReconciliationLineItem] = []
        total_rev = 0.0
        total_cogs = 0.0
        total_comm = 0.0
        discrepancies = 0

        # 1. Process Sales Line Items
        for s in sales:
            client_name = s.client.account_name if s.client else "Client Account"
            sale_dt = FinancialService._ensure_utc(s.sale_date) or now
            if s.payment_status == "paid":
                rev = round(s.amount, 2)
                total_rev += rev
                line_items.append(ReconciliationLineItem(
                    date=sale_dt.isoformat(),
                    transaction_type="client_sale_paid",
                    reference_id=s.order_number,
                    client_or_vendor=client_name,
                    revenue=rev,
                    cogs=0.0,
                    commission=0.0,
                    net_amount=rev,
                    payment_method=s.payment_method,
                    status="settled"
                ))

                # If deal has sales rep attribution, generate corresponding commission line item
                if s.sales_rep_name:
                    rep_key = s.sales_rep_name.lower().strip()
                    comm_rate = rep_rate_map.get(rep_key, 10.0)
                    comm_val = round(s.amount * (comm_rate / 100.0), 2)
                    total_comm += comm_val
                    line_items.append(ReconciliationLineItem(
                        date=sale_dt.isoformat(),
                        transaction_type="rep_commission",
                        reference_id=f"COMM-{s.order_number}",
                        client_or_vendor=f"Rep: {s.sales_rep_name} ({comm_rate}%)",
                        revenue=0.0,
                        cogs=0.0,
                        commission=comm_val,
                        net_amount=-comm_val,
                        payment_method="commission_ledger",
                        status="payable"
                    ))
            else:
                # Unpaid invoice
                line_items.append(ReconciliationLineItem(
                    date=sale_dt.isoformat(),
                    transaction_type="client_sale_invoiced",
                    reference_id=s.order_number,
                    client_or_vendor=client_name,
                    revenue=round(s.amount, 2),
                    cogs=0.0,
                    commission=0.0,
                    net_amount=0.0,
                    payment_method=s.payment_method,
                    status="unsettled"
                ))
                # Discrepancy if invoice unpaid > 30 days
                if (now - sale_dt).days > 30:
                    discrepancies += 1

        # 2. Process Supplier POs (COGS)
        for po in pos:
            cogs_val = round(po.total_cost, 2)
            total_cogs += cogs_val
            sup_name = po.supplier.name if po.supplier else "Supplier Hub"
            po_dt = FinancialService._ensure_utc(po.placed_at) or now
            line_items.append(ReconciliationLineItem(
                date=po_dt.isoformat(),
                transaction_type="supplier_po_cost",
                reference_id=po.po_number,
                client_or_vendor=f"{sup_name} ({po.status})",
                revenue=0.0,
                cogs=cogs_val,
                commission=0.0,
                net_amount=-cogs_val,
                payment_method="supplier_disbursement",
                status="disbursed" if po.status in ["delivered", "shipped", "in_transit"] else "pending_settlement"
            ))

        net_settlement = round(total_rev - total_cogs - total_comm, 2)

        return FinancialReconciliationResponse(
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            total_revenue=round(total_rev, 2),
            total_cogs=round(total_cogs, 2),
            total_commissions=round(total_comm, 2),
            net_settlement=net_settlement,
            unsettled_discrepancies_count=discrepancies,
            line_items=line_items
        )

    @staticmethod
    def export_reconciliation_csv(statement: FinancialReconciliationResponse) -> str:
        """
        Serializes financial reconciliation statement into compliant RFC 4180 CSV string.
        """
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\r\n")

        # Header Comments & Metadata
        writer.writerow(["# Executive Financial Reconciliation Statement"])
        writer.writerow(["# Period Start", statement.period_start])
        writer.writerow(["# Period End", statement.period_end])
        writer.writerow(["# Total Collected Revenue ($)", f"{statement.total_revenue:.2f}"])
        writer.writerow(["# Total Supplier COGS ($)", f"{statement.total_cogs:.2f}"])
        writer.writerow(["# Total Commissions Payable ($)", f"{statement.total_commissions:.2f}"])
        writer.writerow(["# Net Settlement ($)", f"{statement.net_settlement:.2f}"])
        writer.writerow([])

        # Table Column Headers
        writer.writerow([
            "Date",
            "Transaction Type",
            "Reference ID",
            "Client or Vendor",
            "Revenue ($)",
            "COGS ($)",
            "Commission ($)",
            "Net Settlement ($)",
            "Payment Method",
            "Status"
        ])

        # Rows
        for row in statement.line_items:
            writer.writerow([
                row.date,
                row.transaction_type,
                row.reference_id,
                row.client_or_vendor,
                f"{row.revenue:.2f}",
                f"{row.cogs:.2f}",
                f"{row.commission:.2f}",
                f"{row.net_amount:.2f}",
                row.payment_method,
                row.status
            ])

        # Summary Row
        writer.writerow([])
        writer.writerow([
            "SUMMARY TOTALS",
            "",
            "",
            "",
            f"{statement.total_revenue:.2f}",
            f"{statement.total_cogs:.2f}",
            f"{statement.total_commissions:.2f}",
            f"{statement.net_settlement:.2f}",
            "",
            f"Discrepancies: {statement.unsettled_discrepancies_count}"
        ])

        return output.getvalue()

    @staticmethod
    async def compute_rep_commissions(tenant_id: str, db: AsyncSession) -> RepCommissionLeaderboardResponse:
        """
        Computes sales commission breakdown and leaderboard for all organization members.
        """
        # Fetch members and users
        members_stmt = select(OrganizationMembership, User).join(
            User, User.id == OrganizationMembership.user_id
        ).where(OrganizationMembership.organization_id == tenant_id)
        members_res = await db.execute(members_stmt)
        members_rows = members_res.all()

        # Fetch all sales
        sales_stmt = select(ClientSale).where(ClientSale.organization_id == tenant_id)
        sales_res = await db.execute(sales_stmt)
        sales = sales_res.scalars().all()

        reps_summary: List[RepCommissionSummary] = []
        total_commissions = 0.0
        total_sales_volume = 0.0

        for m, u in members_rows:
            rate = float(getattr(m, "commission_rate_pct", 10.0) or 10.0)
            rep_name = u.full_name
            rep_email = u.email

            # Match sales by name or email or assigned rep
            paid_deals = [
                s for s in sales
                if s.sales_rep_name and (
                    s.sales_rep_name.strip().lower() == rep_name.strip().lower() or
                    s.sales_rep_name.strip().lower() == rep_email.strip().lower()
                ) and s.payment_status == "paid"
            ]
            unpaid_deals = [
                s for s in sales
                if s.sales_rep_name and (
                    s.sales_rep_name.strip().lower() == rep_name.strip().lower() or
                    s.sales_rep_name.strip().lower() == rep_email.strip().lower()
                ) and s.payment_status == "unpaid" and s.status != "cancelled"
            ]

            paid_volume = sum(s.amount for s in paid_deals)
            unpaid_volume = sum(s.amount for s in unpaid_deals)
            earned_comm = round(paid_volume * (rate / 100.0), 2)

            total_commissions += earned_comm
            total_sales_volume += paid_volume

            reps_summary.append(RepCommissionSummary(
                user_id=u.id,
                full_name=rep_name,
                email=rep_email,
                role=m.role,
                commission_rate_pct=rate,
                deals_count=len(paid_deals),
                sales_volume=round(paid_volume, 2),
                commission_earned=earned_comm,
                unpaid_pipeline_volume=round(unpaid_volume, 2)
            ))

        # Rank reps by sales volume descending
        reps_summary.sort(key=lambda x: x.sales_volume, reverse=True)

        return RepCommissionLeaderboardResponse(
            reps=reps_summary,
            total_commissions_payable=round(total_commissions, 2),
            total_sales_volume=round(total_sales_volume, 2)
        )

    @staticmethod
    async def update_rep_commission_rate(
        tenant_id: str,
        user_id: str,
        new_rate: float,
        db: AsyncSession,
        actor_email: str = "admin@system",
        actor_role: str = "admin"
    ) -> RepCommissionSummary:
        """
        Updates a member's commission percentage and records an immutable audit log.
        """
        stmt = select(OrganizationMembership, User).join(
            User, User.id == OrganizationMembership.user_id
        ).where(
            OrganizationMembership.organization_id == tenant_id,
            OrganizationMembership.user_id == user_id
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            raise ValueError("Team member not found in this organization.")

        membership, user = row
        old_rate = float(getattr(membership, "commission_rate_pct", 10.0) or 10.0)
        membership.commission_rate_pct = new_rate
        db.add(membership)

        await AuditService.log_event(
            db=db,
            org_id=tenant_id,
            action="team.commission_rate_updated",
            actor_type="user",
            actor_id=user_id,
            actor_email=actor_email,
            actor_role=actor_role,
            target_entity="organization_membership",
            target_id=membership.id,
            status="success",
            payload={
                "target_user_email": user.email,
                "old_commission_rate_pct": old_rate,
                "new_commission_rate_pct": new_rate
            }
        )

        await db.commit()
        await db.refresh(membership)

        # Recalculate summary for this member
        comm_board = await FinancialService.compute_rep_commissions(tenant_id, db)
        for rep in comm_board.reps:
            if rep.user_id == user_id:
                return rep

        return RepCommissionSummary(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=membership.role,
            commission_rate_pct=new_rate,
            deals_count=0,
            sales_volume=0.0,
            commission_earned=0.0,
            unpaid_pipeline_volume=0.0
        )
