import os
import uuid
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import settings
from app.models.tenant import User
from app.services.tenant_provisioning_service import TenantProvisioningService, PLAN_TIER_CONFIG

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["SaaS Billing & Subscriptions"])

class PlanTierInfo(BaseModel):
    tier: str
    name: str
    price: float
    billing: str = "monthly"
    seats: int
    monthly_touches: int
    bots_count: int
    features: List[str]
    included_bots: List[str]

class SaasCheckoutRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=150)
    organization_name: str = Field(..., min_length=2, max_length=150)
    password: str = Field(..., min_length=6, max_length=100)
    plan_tier: str = Field(default="growth")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None

class SaasCheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str
    is_simulation: bool
    plan_tier: str
    organization_id: Optional[str] = None
    token: Optional[str] = None
    message: Optional[str] = None

TIER_BOT_NAMES = {
    "starter": [
        "The Lead Developer Agent"
    ],
    "growth": [
        "The Lead Developer Agent",
        "The Decision-Maker Pathfinder & Literature Bot",
        "The Appointment Setter Agent"
    ],
    "executive": [
        "The Lead Developer Agent",
        "The Decision-Maker Pathfinder & Literature Bot",
        "The Appointment Setter Agent",
        "The Cold Outreach SDR Agent",
        "The Executive Sales Bot",
        "The Objection Closer & Expansion Bot"
    ]
}

@router.get("/plans", response_model=List[PlanTierInfo])
async def get_subscription_plans():
    """
    Returns available SaaS subscription tiers, pricing, bot limits, and feature allocations.
    """
    plans = []
    for tier_key, data in PLAN_TIER_CONFIG.items():
        plans.append(PlanTierInfo(
            tier=tier_key,
            name=data["name"],
            price=data["mrr"],
            billing="monthly",
            seats=data["seats"],
            monthly_touches=data["monthly_quota"],
            bots_count=data["bots_count"],
            features=data["features"],
            included_bots=TIER_BOT_NAMES.get(tier_key, [])
        ))
    return plans

@router.post("/saas-checkout-session", response_model=SaasCheckoutResponse)
async def create_saas_checkout_session(
    payload: SaasCheckoutRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a SaaS subscription checkout session.
    If live Stripe keys are present, generates a Stripe Hosted Subscription Checkout session.
    If live keys are absent or in simulation mode, atomically provisions the tenant,
    generates an active SaaSLicense, and returns instant login credentials.
    """
    # 1. Verify that email is not already registered
    clean_email = payload.email.lower().strip()
    existing_user = await db.execute(select(User).where(User.email == clean_email))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists. Please sign in or use a different email."
        )

    tier = payload.plan_tier.lower().strip()
    if tier not in PLAN_TIER_CONFIG:
        tier = "growth"

    tier_info = PLAN_TIER_CONFIG[tier]

    stripe_key = getattr(settings, "STRIPE_SECRET_KEY", None) or os.getenv("STRIPE_SECRET_KEY")
    is_live = bool(
        stripe_key
        and str(stripe_key).startswith("sk_")
        and not str(stripe_key).startswith("sk_test_")
        and not str(stripe_key).startswith("sk_mock_")
    )

    if is_live:
        try:
            import stripe
            stripe.api_key = stripe_key
            success_url = payload.success_url or "https://therealbonz.com/JsProject/console?welcome=1&session_id={CHECKOUT_SESSION_ID}"
            cancel_url = payload.cancel_url or "https://therealbonz.com/JsProject/signup?cancelled=1"

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"NexFlow AI {tier_info['name']} Subscription",
                            "description": f"{tier_info['bots_count']} AI Sales Bots, {tier_info['seats']} seats, {tier_info['monthly_quota']} monthly touches",
                        },
                        "unit_amount": int(round(tier_info["mrr"] * 100)),
                        "recurring": {"interval": "month"},
                    },
                    "quantity": 1,
                }],
                mode="subscription",
                customer_email=clean_email,
                metadata={
                    "type": "saas_subscription",
                    "plan_tier": tier,
                    "email": clean_email,
                    "full_name": payload.full_name,
                    "organization_name": payload.organization_name,
                    "raw_password": payload.password
                },
                success_url=success_url,
                cancel_url=cancel_url,
            )

            return SaasCheckoutResponse(
                checkout_url=session.url,
                session_id=session.id,
                is_simulation=False,
                plan_tier=tier,
                message=f"Hosted Stripe checkout generated for {tier_info['name']}."
            )
        except Exception as e:
            logger.warning(f"Stripe live subscription creation encountered error ({e}); falling back to zero-friction simulation")

    # Simulation / Local-First Provisioning
    sim_session_id = f"cs_sim_{uuid.uuid4().hex[:18]}"
    provision_res = await TenantProvisioningService.provision_saas_tenant(
        db=db,
        organization_name=payload.organization_name,
        full_name=payload.full_name,
        email=clean_email,
        password=payload.password,
        plan_tier=tier,
        stripe_customer_id=f"cus_sim_{uuid.uuid4().hex[:14]}",
        stripe_subscription_id=f"sub_sim_{uuid.uuid4().hex[:14]}"
    )

    token = provision_res["access_token"]
    org_id = provision_res["organization_id"]
    checkout_url = f"/console?welcome=1&plan={tier}&token={token}"

    return SaasCheckoutResponse(
        checkout_url=checkout_url,
        session_id=sim_session_id,
        is_simulation=True,
        plan_tier=tier,
        organization_id=org_id,
        token=token,
        message=f"Account and {tier_info['name']} bot workforce provisioned successfully!"
    )

@router.post("/saas-webhook")
async def handle_saas_stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Public webhook listener for live Stripe subscription events.
    Fulfills new SaaS account provisioning when checkout.session.completed fires.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    event_type = body.get("type", "checkout.session.completed")
    data_object = body.get("data", {}).get("object", {})
    metadata = data_object.get("metadata", {})

    if metadata.get("type") != "saas_subscription":
        return {"received": True, "message": "Ignored - not a SaaS subscription checkout event"}

    email = metadata.get("email")
    org_name = metadata.get("organization_name")
    full_name = metadata.get("full_name")
    password = metadata.get("raw_password", f"TempPass_{uuid.uuid4().hex[:8]}")
    plan_tier = metadata.get("plan_tier", "growth")
    stripe_customer_id = data_object.get("customer")
    stripe_subscription_id = data_object.get("subscription")

    # Check if already provisioned (idempotency)
    clean_email = email.lower().strip() if email else ""
    existing = await db.execute(select(User).where(User.email == clean_email))
    if existing.scalar_one_or_none():
        logger.info(f"[SAAS WEBHOOK] Account {clean_email} already provisioned. Acknowledging webhook.")
        return {"received": True, "status": "already_provisioned"}

    provision_res = await TenantProvisioningService.provision_saas_tenant(
        db=db,
        organization_name=org_name or "New SaaS Client",
        full_name=full_name or "Primary Administrator",
        email=clean_email,
        password=password,
        plan_tier=plan_tier,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id
    )

    logger.info(f"[SAAS WEBHOOK PROVISIONED] Successfully provisioned tenant for {clean_email} via webhook")
    return {
        "received": True,
        "status": "provisioned",
        "organization_id": provision_res["organization_id"],
        "plan_tier": plan_tier
    }
