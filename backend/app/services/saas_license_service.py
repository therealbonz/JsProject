from datetime import datetime, timezone, timedelta
import hashlib
import json
import logging
import uuid
from typing import Optional, List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.models.tenant import Organization, User
from app.models.crm import Company, Contact, ClientAccount, ClientSale, SaaSLicense, SaaSExpansionProposal
from app.models.hitl import HumanAssistanceRequest, AuditLog
from app.services.gemini_service import gemini_service
from app.services.order_filler.agent import OrderFillerAgent, order_filler_agent
from app.services.stripe_recurring_service import StripeRecurringService
from app.services.demand_forecast_service import DemandForecastService

logger = logging.getLogger(__name__)

class SaaSLicenseService:
    @staticmethod
    def generate_license_key(plan_tier: str) -> str:
        """Generates a formatted, unique license key (e.g. LIC-ENT-4F8A-9C12-88B0)."""
        tier_code = (plan_tier or "PRO")[:3].upper()
        u1 = uuid.uuid4().hex[:4].upper()
        u2 = uuid.uuid4().hex[:4].upper()
        u3 = uuid.uuid4().hex[:4].upper()
        return f"LIC-{tier_code}-{u1}-{u2}-{u3}"

    @staticmethod
    def generate_license_token(org_id: str, client_id: str, license_key: str) -> str:
        """Generates a cryptographic activation token signature."""
        payload = f"{org_id}:{client_id}:{license_key}:{datetime.now(timezone.utc).isoformat()}"
        sig = hashlib.sha256(payload.encode()).hexdigest()[:32]
        return f"token_v1_{sig}"

    @staticmethod
    def calculate_health(
        licensed_seats: int,
        active_seats_used: int,
        quota_units: int,
        quota_used: int,
        days_until_renewal: int,
        is_initial: bool = False
    ) -> tuple[int, str, str]:
        """
        Calculates SaaS client health score (0-100), churn risk level, and rationale.
        """
        if is_initial:
            return 95, "healthy", "Newly provisioned license in onboarding."

        score = 100
        reasons = []

        # 1. Seat adoption evaluation
        util_pct = (active_seats_used / licensed_seats * 100) if licensed_seats > 0 else 0
        if util_pct < 20.0:
            score -= 35
            reasons.append(f"Severely low seat utilization ({util_pct:.1f}%). Low team adoption indicates high churn risk.")
        elif util_pct < 50.0:
            score -= 15
            reasons.append(f"Moderate seat utilization ({util_pct:.1f}%). Onboarding may have stalled.")
        elif 75.0 <= util_pct <= 95.0:
            score += 5
            reasons.append(f"Optimal healthy seat utilization ({util_pct:.1f}%). High product engagement.")
        elif util_pct > 95.0:
            score -= 5
            reasons.append(f"Near full seat capacity ({util_pct:.1f}%). Client requires expansion add-on.")

        # 2. Resource / Quota consumption evaluation
        if quota_units > 0:
            q_util = (quota_used / quota_units * 100)
            if q_util < 10.0:
                score -= 10
                reasons.append("Very low API/resource usage over the current billing cycle.")
            elif q_util > 95.0:
                reasons.append(f"Heavy API quota consumption ({q_util:.1f}%). Potential overage.")

        # 3. Renewal proximity risk
        if days_until_renewal <= 30 and util_pct < 40.0:
            score -= 25
            reasons.append("Contract renews in <30 days with under-utilized license seats.")

        # Bound score between 5 and 100
        score = max(5, min(100, score))

        if score >= 80:
            level = "healthy"
        elif score >= 60:
            level = "monitor"
        elif score >= 40:
            level = "at_risk"
        else:
            level = "critical"

        rationale = " | ".join(reasons) if reasons else "Strong account telemetry and consistent seat activity."
        return score, level, rationale

    async def provision_license(
        self,
        db: AsyncSession,
        org: Organization,
        user: Optional[User],
        client_account_id: str,
        plan_tier: str = "pro",
        product_name: str = "Enterprise AI Platform",
        billing_interval: str = "annual",
        licensed_seats: int = 25,
        seat_unit_price: float = 50.0,
        monthly_quota_units: int = 100000,
        overage_allowed: bool = True,
        overage_unit_rate: float = 0.05,
        auto_renew: bool = True,
        features_enabled: Optional[List[str]] = None,
        notes: Optional[str] = None
    ) -> SaaSLicense:
        """
        Creates and provisions a new SaaS license, generates cryptographic key/token,
        and computes initial MRR/ARR.
        """
        # Fetch client account
        client_stmt = select(ClientAccount).options(
            selectinload(ClientAccount.company),
            selectinload(ClientAccount.primary_contact)
        ).where(
            ClientAccount.id == client_account_id,
            ClientAccount.organization_id == org.id
        )
        res = await db.execute(client_stmt)
        client = res.scalar_one_or_none()
        if not client:
            raise ValueError("ClientAccount not found in this organization")

        now = datetime.now(timezone.utc)
        renewal_days = 365 if billing_interval in ["annual", "multi_year"] else (90 if billing_interval == "quarterly" else 30)
        renewal_dt = now + timedelta(days=renewal_days)

        mrr = float(licensed_seats * seat_unit_price)
        arr = float(mrr * 12)

        key = self.generate_license_key(plan_tier)
        token = self.generate_license_token(org.id, client.id, key)

        active_initial = max(1, min(licensed_seats, 5))
        util_pct = round((active_initial / licensed_seats) * 100, 1)

        health_score, churn_risk, rationale = self.calculate_health(
            licensed_seats=licensed_seats,
            active_seats_used=active_initial,
            quota_units=monthly_quota_units,
            quota_used=int(monthly_quota_units * 0.1),
            days_until_renewal=renewal_days,
            is_initial=True
        )

        license_obj = SaaSLicense(
            organization_id=org.id,
            client_id=client.id,
            company_id=client.company_id,
            primary_contact_id=client.primary_contact_id,
            license_key=key,
            license_token=token,
            product_name=product_name,
            plan_tier=plan_tier.lower(),
            license_status="active",
            billing_interval=billing_interval.lower(),
            seat_unit_price=seat_unit_price,
            licensed_seats=licensed_seats,
            active_seats_used=active_initial,
            seat_utilization_pct=util_pct,
            monthly_quota_units=monthly_quota_units,
            current_quota_used=int(monthly_quota_units * 0.1),
            overage_allowed=overage_allowed,
            overage_unit_rate=overage_unit_rate,
            mrr=mrr,
            arr=arr,
            auto_renew=auto_renew,
            contract_start_date=now,
            renewal_date=renewal_dt,
            last_telemetry_at=now,
            health_score=health_score,
            churn_risk_level=churn_risk,
            health_rationale=rationale,
            features_enabled=features_enabled or ["hitl_guardrails", "ai_order_filler", "api_access"],
            notes=notes or f"Provisioned {plan_tier.upper()} tier with {licensed_seats} seats."
        )
        db.add(license_obj)

        audit = AuditLog(
            organization_id=org.id,
            actor_type="system" if not user else "human_rep",
            actor_id=user.id if user else "saas_provisioning_bot",
            action="saas_license_provisioned",
            target_entity="saas_license",
            target_id=license_obj.id,
            payload={
                "license_key": key,
                "plan_tier": plan_tier,
                "licensed_seats": licensed_seats,
                "mrr": mrr,
                "client_name": client.account_name
            }
        )
        db.add(audit)
        await db.commit()
        await db.refresh(license_obj)
        return license_obj

    async def ingest_telemetry(
        self,
        db: AsyncSession,
        license_id: str,
        active_seats: int,
        quota_used: int,
        daily_active_users: Optional[int] = None,
        api_calls_count: Optional[int] = None
    ) -> SaaSLicense:
        """
        Updates live usage telemetry, updates seat utilization percentage,
        re-evaluates health score and churn risk.
        """
        stmt = select(SaaSLicense).where(SaaSLicense.id == license_id)
        res = await db.execute(stmt)
        lic = res.scalar_one_or_none()
        if not lic:
            raise ValueError("SaaSLicense not found")

        now = datetime.now(timezone.utc)
        lic.active_seats_used = active_seats
        lic.current_quota_used = quota_used
        lic.last_telemetry_at = now

        util_pct = (active_seats / lic.licensed_seats * 100) if lic.licensed_seats > 0 else 0
        lic.seat_utilization_pct = round(util_pct, 1)

        days_left = 365
        if lic.renewal_date:
            ren = lic.renewal_date
            if ren.tzinfo is None:
                ren = ren.replace(tzinfo=timezone.utc)
            days_left = max(0, (ren - now).days)
        score, level, rationale = self.calculate_health(
            licensed_seats=lic.licensed_seats,
            active_seats_used=lic.active_seats_used,
            quota_units=lic.monthly_quota_units,
            quota_used=lic.current_quota_used,
            days_until_renewal=days_left
        )
        lic.health_score = score
        lic.churn_risk_level = level
        lic.health_rationale = rationale

        await db.commit()
        await db.refresh(lic)
        return lic

    async def run_expansion_audit(
        self,
        db: AsyncSession,
        org: Organization,
        requested_discount_pct: float = 0.0
    ) -> Dict[str, Any]:
        """
        Autonomous PQL Expansion Bot:
        Scans all active SaaS licenses for expansion signals:
        - Seat utilization >= 85.0% OR
        - Quota consumption >= 90.0%
        Drafts customized upgrade proposal and enforces HITL guardrails.
        """
        stmt = select(SaaSLicense).options(
            selectinload(SaaSLicense.client),
            selectinload(SaaSLicense.company),
            selectinload(SaaSLicense.primary_contact)
        ).where(
            SaaSLicense.organization_id == org.id,
            SaaSLicense.license_status == "active"
        )
        res = await db.execute(stmt)
        licenses = res.scalars().all()

        max_allowed_discount = getattr(org, "max_discount_pct", 10.0) or 10.0
        proposals_generated = []

        for lic in licenses:
            is_seat_hot = lic.seat_utilization_pct >= 85.0
            is_quota_hot = (lic.monthly_quota_units > 0 and (lic.current_quota_used / lic.monthly_quota_units) >= 0.90)

            if is_seat_hot or is_quota_hot:
                # Calculate proposed expansion
                expansion_seats = max(10, int(lic.licensed_seats * 0.5))  # +50% seats
                new_seats = lic.licensed_seats + expansion_seats
                new_mrr = new_seats * lic.seat_unit_price * (1 - (requested_discount_pct / 100.0))
                arr_delta = (new_mrr - lic.mrr) * 12

                # Check HITL discount guardrail
                requires_hitl = requested_discount_pct > max_allowed_discount
                hitl_req_id = None

                # Generate AI Outreach Draft
                client_name = lic.client.account_name if lic.client else "Valued Client"
                contact_name = lic.primary_contact.first_name if lic.primary_contact else "Team Lead"

                ai_draft = (
                    f"Subject: Scaling your {lic.product_name} Capacity • {client_name}\n\n"
                    f"Hi {contact_name},\n\n"
                    f"Our autonomous telemetry monitor noted that your team has reached {lic.seat_utilization_pct:.1f}% "
                    f"of your {lic.licensed_seats} licensed seats ({lic.active_seats_used} active users).\n\n"
                    f"To ensure uninterrupted access and avoid seat contention across your departments, "
                    f"we have prepared an expansion package adding +{expansion_seats} seats (Total: {new_seats} seats) "
                    f"at an ARR delta of ${arr_delta:,.2f}.\n\n"
                    f"Would you like our engineering team to automatically provision these seats to your license key ({lic.license_key})?\n\n"
                    f"Best regards,\n"
                    f"Autonomous Account Expansion Team"
                )

                if requires_hitl:
                    # Halt and create HITL request
                    hitl_req = HumanAssistanceRequest(
                        organization_id=org.id,
                        lead_id=None,
                        conversation_id=None,
                        trigger_reason="policy_discount",
                        situation_summary=f"Expansion proposal for {client_name} requests {requested_discount_pct:.1f}% discount on +{expansion_seats} seats (exceeds tenant limit of {max_allowed_discount:.1f}%).",
                        suggested_options=["Approve Requested Discount", "Reject and Offer Standard Pricing"],
                        ai_recommendation=f"Approve or adjust discount for {client_name} license {lic.license_key} (+${arr_delta:,.2f} ARR).",
                        confidence_score=0.90,
                        status="pending"
                    )
                    db.add(hitl_req)
                    await db.flush()
                    hitl_req_id = hitl_req.id

                # Save proposal record
                proposal = SaaSExpansionProposal(
                    organization_id=org.id,
                    license_id=lic.id,
                    proposal_type="seat_expansion" if is_seat_hot else "quota_boost",
                    trigger_reason=f"Seat utilization reached {lic.seat_utilization_pct:.1f}% ({lic.active_seats_used}/{lic.licensed_seats} seats)" if is_seat_hot else "API quota consumption reached 90%+",
                    current_seats=lic.licensed_seats,
                    proposed_seats=new_seats,
                    current_mrr=lic.mrr,
                    proposed_mrr=new_mrr,
                    arr_delta=arr_delta,
                    discount_pct=requested_discount_pct,
                    requires_hitl_approval=requires_hitl,
                    hitl_request_id=hitl_req_id,
                    ai_drafted_outreach=ai_draft,
                    status="pending" if requires_hitl else "approved",
                    sent_at=datetime.now(timezone.utc) if not requires_hitl else None
                )
                db.add(proposal)
                await db.flush()

                proposals_generated.append({
                    "license_id": lic.id,
                    "license_key": lic.license_key,
                    "client_name": client_name,
                    "plan_tier": lic.plan_tier,
                    "licensed_seats": lic.licensed_seats,
                    "active_seats_used": lic.active_seats_used,
                    "seat_utilization_pct": lic.seat_utilization_pct,
                    "current_mrr": lic.mrr,
                    "proposed_new_seats": new_seats,
                    "proposed_new_mrr": new_mrr,
                    "arr_delta": arr_delta,
                    "discount_pct": requested_discount_pct,
                    "requires_hitl": requires_hitl,
                    "ai_drafted_outreach": ai_draft,
                    "proposal_id": proposal.id
                })

        await db.commit()
        return {
            "total_licenses_scanned": len(licenses),
            "expansion_candidates_found": len(proposals_generated),
            "proposals_generated": proposals_generated
        }

    async def run_renewal_radar(
        self,
        db: AsyncSession,
        org: Organization,
        lookahead_days: int = 60
    ) -> Dict[str, Any]:
        """
        Autonomous Churn Defense & Renewal Bot:
        Scans upcoming contract renewals (within lookahead_days) and at-risk health scores.
        If auto-charge is enabled on the client account, processes renewal sale and extends term.
        """
        stmt = select(SaaSLicense).options(
            selectinload(SaaSLicense.client),
            selectinload(SaaSLicense.company),
            selectinload(SaaSLicense.primary_contact)
        ).where(
            SaaSLicense.organization_id == org.id,
            SaaSLicense.license_status == "active"
        )
        res = await db.execute(stmt)
        licenses = res.scalars().all()

        now = datetime.now(timezone.utc)
        items = []
        expiring_count = 0
        at_risk_count = 0

        stripe_service = StripeRecurringService()

        for lic in licenses:
            days_left = 999
            if lic.renewal_date:
                ren = lic.renewal_date
                if ren.tzinfo is None:
                    ren = ren.replace(tzinfo=timezone.utc)
                days_left = (ren - now).days
            is_expiring = days_left <= lookahead_days
            is_at_risk = lic.health_score < 60

            if is_expiring or is_at_risk:
                if is_expiring:
                    expiring_count += 1
                if is_at_risk:
                    at_risk_count += 1

                client_name = lic.client.account_name if lic.client else "Client"
                auto_charged = False
                renewal_sale_id = None
                action = "Manual Account Review"

                # Check if can auto-renew with card on file
                if is_expiring and lic.auto_renew and lic.client and lic.client.has_payment_method_on_file and lic.client.auto_charge_enabled:
                    # Create renewal order
                    renewal_order_num = f"SO-RENEW-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
                    renewal_amount = lic.arr if lic.billing_interval in ["annual", "multi_year"] else lic.mrr

                    sale = ClientSale(
                        organization_id=org.id,
                        client_id=lic.client.id,
                        order_number=renewal_order_num,
                        amount=renewal_amount,
                        sale_date=now,
                        status="completed",
                        payment_method="card_on_file",
                        payment_status="paid",
                        auto_fulfill_on_payment=True,
                        items_summary=f"Annual Renewal: {lic.licensed_seats} Seats • {lic.product_name} ({lic.plan_tier.upper()})",
                        sales_rep_name="Autonomous Renewal Bot",
                        notes=f"Auto-renewed subscription for license {lic.license_key}"
                    )
                    db.add(sale)
                    await db.flush()

                    # Extend license renewal date by 365 days
                    lic.renewal_date = lic.renewal_date + timedelta(days=365)
                    lic.current_quota_used = 0  # reset quota for new period
                    lic.client.total_revenue += renewal_amount
                    lic.client.order_count += 1

                    auto_charged = True
                    renewal_sale_id = sale.id
                    action = "Auto-Renewed & Charged Stored Card"

                    audit = AuditLog(
                        organization_id=org.id,
                        actor_type="system",
                        actor_id="saas_renewal_bot",
                        action="saas_license_auto_renewed",
                        target_entity="saas_license",
                        target_id=lic.id,
                        payload={"license_key": lic.license_key, "amount": renewal_amount, "new_renewal_date": lic.renewal_date.isoformat()}
                    )
                    db.add(audit)
                elif is_at_risk:
                    action = f"Trigger Retention Playbook: {lic.health_rationale}"
                else:
                    action = f"Generate Renewal Quote Invoice ({days_left} days remaining)"

                items.append({
                    "license_id": lic.id,
                    "license_key": lic.license_key,
                    "client_name": client_name,
                    "renewal_date": lic.renewal_date,
                    "days_until_renewal": days_left,
                    "health_score": lic.health_score,
                    "churn_risk_level": lic.churn_risk_level,
                    "arr": lic.arr,
                    "action_recommended": action,
                    "auto_charged": auto_charged,
                    "renewal_sale_id": renewal_sale_id
                })

        await db.commit()
        return {
            "total_licenses_scanned": len(licenses),
            "expiring_soon_count": expiring_count,
            "at_risk_count": at_risk_count,
            "items": items
        }

    async def provision_cloud_resources(
        self,
        db: AsyncSession,
        org: Organization,
        license_id: str,
        cloud_provider: str = "amazon_aws",
        resource_spec: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Integrates Order Filler Agent (CRM 3 Bot) to autonomously provision cloud
        infrastructure, container seats, or developer tokens for the license.
        """
        stmt = select(SaaSLicense).options(
            selectinload(SaaSLicense.client),
            selectinload(SaaSLicense.company)
        ).where(
            SaaSLicense.id == license_id,
            SaaSLicense.organization_id == org.id
        )
        res = await db.execute(stmt)
        lic = res.scalar_one_or_none()
        if not lic:
            raise ValueError("SaaSLicense not found")

        prompt = (
            f"Autonomous cloud provisioning order: {lic.licensed_seats} enterprise seats for {lic.product_name} "
            f"({lic.plan_tier} tier). Resource spec: {resource_spec or 'Cloud Instance Pool & API Quota Provisioning'}."
        )

        # Map cloud provider to supplier code
        supplier_code = "amazon_business" if "amazon" in cloud_provider.lower() else ("digikey" if "digikey" in cloud_provider.lower() else "grainger")

        # Invoke Order Filler Agent
        fill_res = await order_filler_agent.auto_fill_order(
            db=db,
            org_id=org.id,
            prompt=prompt,
            preferred_supplier_code=supplier_code,
            destination_type="cloud_provisioning",
            destination_address=f"Cloud Region us-east-1 • Virtual VPC for {lic.company.name if lic.company else 'Client'}",
            max_budget_limit=2500.0
        )

        supplier_name = fill_res.get("supplier") or fill_res.get("supplier_name") or "Cloud Partner Network"
        tracking_num = fill_res.get("tracking_number")

        return {
            "license_id": lic.id,
            "license_key": lic.license_key,
            "purchase_order_id": fill_res.get("purchase_order_id"),
            "po_number": fill_res.get("po_number"),
            "supplier_name": supplier_name,
            "provisioning_status": "provisioned_dispatched",
            "tracking_number": tracking_num,
            "tracking_url": f"https://track.cloudprovider.internal/{tracking_num}" if tracking_num else None,
            "message": f"Autonomous Cloud Provisioner dispatched resources via {supplier_name} for {lic.licensed_seats} seats."
        }

    async def get_overview_metrics(
        self,
        db: AsyncSession,
        org_id: str
    ) -> Dict[str, Any]:
        """Calculates macro-level SaaS portfolio KPIs."""
        stmt = select(SaaSLicense).where(SaaSLicense.organization_id == org_id)
        res = await db.execute(stmt)
        licenses = res.scalars().all()

        total = len(licenses)
        active = sum(1 for l in licenses if l.license_status == "active")
        total_arr = sum(l.arr for l in licenses if l.license_status == "active")
        total_mrr = sum(l.mrr for l in licenses if l.license_status == "active")
        licensed_seats = sum(l.licensed_seats for l in licenses if l.license_status == "active")
        active_seats = sum(l.active_seats_used for l in licenses if l.license_status == "active")

        avg_util = (active_seats / licensed_seats * 100) if licensed_seats > 0 else 0.0

        healthy = sum(1 for l in licenses if l.churn_risk_level == "healthy")
        monitor = sum(1 for l in licenses if l.churn_risk_level == "monitor")
        at_risk = sum(1 for l in licenses if l.churn_risk_level == "at_risk")
        critical = sum(1 for l in licenses if l.churn_risk_level == "critical")

        return {
            "total_licenses": total,
            "active_licenses": active,
            "total_arr": round(total_arr, 2),
            "total_mrr": round(total_mrr, 2),
            "total_licensed_seats": licensed_seats,
            "total_active_seats": active_seats,
            "avg_seat_utilization_pct": round(avg_util, 1),
            "healthy_count": healthy,
            "monitor_count": monitor,
            "at_risk_count": at_risk,
            "critical_count": critical
        }

saas_license_service = SaaSLicenseService()
