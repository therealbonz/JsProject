import re
import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import hash_password, create_access_token
from app.models.tenant import Organization, User, OrganizationMembership, AIConfiguration
from app.models.crm import Company, Contact, ClientAccount, SaaSLicense, Product, Lead

logger = logging.getLogger(__name__)

def slugify(text: str) -> str:
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug).strip('-')
    return slug or f"org-{uuid.uuid4().hex[:6]}"

PLAN_TIER_CONFIG = {
    "starter": {
        "name": "Starter SDR",
        "mrr": 199.0,
        "seats": 2,
        "monthly_quota": 1000,
        "autonomy": "assistant",
        "bots_count": 1,
        "features": [
            "lead_dev",
            "appointment_setter",
            "calendar_integration",
            "email_notifications"
        ]
    },
    "growth": {
        "name": "Growth Team",
        "mrr": 499.0,
        "seats": 5,
        "monthly_quota": 5000,
        "autonomy": "semi_autonomous",
        "bots_count": 3,
        "features": [
            "lead_dev",
            "decision_maker_discovery",
            "appointment_setter",
            "outbound_sdr",
            "voice_switchboard_ai",
            "postal_collateral_dispatch",
            "multi_channel_cadences"
        ]
    },
    "executive": {
        "name": "Executive Workforce",
        "mrr": 1499.0,
        "seats": 20,
        "monthly_quota": 25000,
        "autonomy": "autonomous",
        "bots_count": 6,
        "features": [
            "lead_dev",
            "decision_maker_discovery",
            "appointment_setter",
            "outbound_sdr",
            "exec_closer",
            "objection_closer",
            "voice_switchboard_ai",
            "postal_collateral_dispatch",
            "executive_deal_dossiers",
            "custom_contract_concessions",
            "dedicated_hitl_queue"
        ]
    }
}

class TenantProvisioningService:

    @classmethod
    async def provision_saas_tenant(
        cls,
        db: AsyncSession,
        organization_name: str,
        full_name: str,
        email: str,
        password: str,
        plan_tier: str = "growth",
        stripe_customer_id: Optional[str] = None,
        stripe_subscription_id: Optional[str] = None,
        billing_interval: str = "monthly"
    ) -> Dict[str, Any]:
        """
        Atomically provisions a complete new tenant:
        1. Organization with unique slug
        2. Admin User with hashed credentials
        3. OrganizationMembership (role: admin)
        4. Tuned AIConfiguration for the active bot tier
        5. Default Company, Contact, and ClientAccount
        6. Active SaaSLicense with verified seat & quota limits
        7. Starter product catalog and initial sales pipeline
        8. Generates JWT access token
        """
        normalized_tier = plan_tier.lower().strip()
        if normalized_tier not in PLAN_TIER_CONFIG:
            normalized_tier = "growth"
        
        tier_info = PLAN_TIER_CONFIG[normalized_tier]

        # 1. Ensure Slug Uniqueness
        base_slug = slugify(organization_name)
        slug = base_slug
        existing_slug = await db.execute(select(Organization).where(Organization.slug == slug))
        if existing_slug.scalar_one_or_none():
            slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        # 2. Create Organization
        org = Organization(
            name=organization_name,
            slug=slug,
            status="active",
            brand_name=organization_name,
            brand_accent_color="#4f46e5" if normalized_tier != "executive" else "#7c3aed",
            support_email=email
        )
        db.add(org)
        await db.flush()

        # 3. Create Admin User
        user = User(
            email=email.lower().strip(),
            hashed_password=hash_password(password),
            full_name=full_name.strip(),
            is_active=True,
            is_superuser=False
        )
        db.add(user)
        await db.flush()

        # 4. Create Organization Admin Membership
        membership = OrganizationMembership(
            organization_id=org.id,
            user_id=user.id,
            role="admin",
            commission_rate_pct=10.0
        )
        db.add(membership)

        # 5. Create AIConfiguration tuned to the plan tier
        ai_config = AIConfiguration(
            organization_id=org.id,
            company_name=org.name,
            company_description=f"Autonomous B2B SaaS Sales Workforce for {org.name}.",
            autonomy_level=tier_info["autonomy"],
            max_discount_pct=15.0 if normalized_tier == "executive" else 10.0,
            tone_of_voice="executive, consultative, data-driven, and proactive",
            prohibited_phrases=["unlimited free service", "guaranteed 1000x return"],
            sales_guidelines=(
                "Qualify decision makers swiftly. Navigate switchboards using polite consultative inquiries. "
                "Secure permission before dispatching digital or postal whitepapers. "
                "Prioritize demo bookings with verified budget holders."
            ),
            hitl_required_for_closing=(normalized_tier != "executive")
        )
        db.add(ai_config)

        # 6. Create Primary Company, Contact & ClientAccount records
        primary_company = Company(
            organization_id=org.id,
            name=org.name,
            domain=f"{slug}.example.com",
            industry="Software & Technology",
            employee_range="10-50",
            notes=f"Initial primary corporate account for {org.name} on {tier_info['name']}."
        )
        db.add(primary_company)
        await db.flush()

        name_parts = full_name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else "Executive"

        primary_contact = Contact(
            organization_id=org.id,
            company_id=primary_company.id,
            first_name=first_name,
            last_name=last_name,
            email=email.lower().strip(),
            job_title="Managing Director / Owner",
            decision_maker_role="purchasing",
            is_primary=True
        )
        db.add(primary_contact)
        await db.flush()

        client_account = ClientAccount(
            organization_id=org.id,
            company_id=primary_company.id,
            primary_contact_id=primary_contact.id,
            account_name=org.name,
            account_tier="enterprise" if normalized_tier == "executive" else "standard",
            status="active",
            stripe_customer_id=stripe_customer_id,
            portal_access_token=f"portal_{uuid.uuid4().hex[:24]}"
        )
        db.add(client_account)
        await db.flush()

        # 7. Create Active SaaSLicense
        license_key = f"NEX-{normalized_tier.upper()}-{uuid.uuid4().hex[:4].upper()}-{uuid.uuid4().hex[:4].upper()}"
        now = datetime.now(timezone.utc)
        renewal = now + timedelta(days=30 if billing_interval == "monthly" else 365)

        mrr_val = tier_info["mrr"]
        license_record = SaaSLicense(
            organization_id=org.id,
            client_id=client_account.id,
            company_id=primary_company.id,
            primary_contact_id=primary_contact.id,
            license_key=license_key,
            license_token=f"tok_{uuid.uuid4().hex}",
            product_name="NexFlow AI Sales Workforce",
            plan_tier=normalized_tier,
            license_status="active",
            billing_interval=billing_interval,
            seat_unit_price=50.0,
            licensed_seats=tier_info["seats"],
            active_seats_used=1,
            seat_utilization_pct=round((1 / tier_info["seats"]) * 100, 1),
            monthly_quota_units=tier_info["monthly_quota"],
            current_quota_used=0,
            overage_allowed=True,
            overage_unit_rate=0.005,
            mrr=mrr_val,
            arr=mrr_val * 12,
            auto_renew=True,
            contract_start_date=now,
            renewal_date=renewal,
            health_score=100,
            churn_risk_level="healthy",
            features_enabled=tier_info["features"],
            notes=f"Automated self-serve signup on {tier_info['name']} tier."
        )
        db.add(license_record)

        # 8. Seed Starter Catalog Products
        sample_products = [
            Product(
                organization_id=org.id,
                name="Autonomous Sales Bot Seat",
                sku="BOT-SEAT-01",
                category="AI Subscriptions",
                description="Dedicated AI sales agent runtime worker for pipeline acceleration.",
                unit_price=tier_info["mrr"],
                min_allowed_price=tier_info["mrr"] * 0.9,
                currency="USD",
                is_active=True
            ),
            Product(
                organization_id=org.id,
                name="Postal Briefing Collateral Dispatch Unit",
                sku="LIT-POSTAL-01",
                category="Marketing Literature",
                description="Physical premium executive briefing pack mailed to decision makers.",
                unit_price=14.50,
                min_allowed_price=12.00,
                currency="USD",
                is_active=True
            )
        ]
        for p in sample_products:
            db.add(p)

        # 9. Seed Initial Demo Prospect Lead to jump-start the pipeline
        demo_lead_company = Company(
            organization_id=org.id,
            name="Apex Dynamics Cloud",
            domain="apexdynamics.example",
            industry="Enterprise Cloud Architecture",
            employee_range="50-200",
            notes="Target prospect for AI sales qualification."
        )
        db.add(demo_lead_company)
        await db.flush()

        demo_contact = Contact(
            organization_id=org.id,
            company_id=demo_lead_company.id,
            first_name="Marcus",
            last_name="Vance",
            email="marcus.vance@apexdynamics.example",
            job_title="VP of Engineering & Architecture",
            decision_maker_role="purchasing",
            is_primary=True
        )
        db.add(demo_contact)
        await db.flush()

        demo_lead = Lead(
            organization_id=org.id,
            company_id=demo_lead_company.id,
            contact_id=demo_contact.id,
            lead_score=85,
            pipeline_stage="new",
            status="active",
            assigned_agent_id="discovery",
            notes="Inbound discovery target: decision-maker identified; pending literature dispatch."
        )
        db.add(demo_lead)

        await db.commit()
        await db.refresh(org)
        await db.refresh(user)
        await db.refresh(license_record)

        # 10. Generate JWT Access Token
        access_token = create_access_token({
            "sub": user.id,
            "org_id": org.id,
            "role": "admin",
            "plan_tier": normalized_tier
        })

        logger.info(
            f"[TENANT PROVISIONED] Org '{org.name}' ({org.id}) provisioned successfully. "
            f"User: {user.email}, License: {license_record.license_key}, Tier: {normalized_tier}"
        )

        return {
            "success": True,
            "organization_id": org.id,
            "organization_name": org.name,
            "organization_slug": org.slug,
            "user_id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "plan_tier": normalized_tier,
            "plan_name": tier_info["name"],
            "license_key": license_record.license_key,
            "mrr": license_record.mrr,
            "access_token": access_token
        }
