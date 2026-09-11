import secrets
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.api.deps import get_current_tenant, require_roles
from app.models.tenant import User, Organization
from app.models.developer import ApiKey, WebhookSubscription, WebhookDeliveryLog
from app.schemas.developer import (
    ApiKeyCreateRequest,
    ApiKeyCreatedResponse,
    ApiKeyListItemResponse,
    WebhookSubscriptionCreateRequest,
    WebhookSubscriptionUpdateRequest,
    WebhookSubscriptionCreatedResponse,
    WebhookSubscriptionResponse,
    WebhookDeliveryLogResponse,
    WebhookPingResponse,
    EventCatalogItemResponse
)
from app.services.webhook_service import WebhookService
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/developer", tags=["Developer Platform & Webhooks"])

DEVELOPER_ROLES = ["admin", "sales_manager"]

SUPPORTED_EVENTS = [
    {
        "event_type": "order.created",
        "description": "Triggered when a new B2B client sale or order draft is recorded.",
        "example_payload": {
            "order_number": "SO-2026-0042",
            "client_name": "Apex Global Logistics",
            "amount": 2450.00,
            "currency": "USD",
            "items_summary": "10x Heavy Duty Actuators",
            "status": "pending"
        }
    },
    {
        "event_type": "payment.succeeded",
        "description": "Triggered when a Stripe invoice, card-on-file charge, or credit terms payment settles.",
        "example_payload": {
            "order_number": "SO-2026-0042",
            "client_name": "Apex Global Logistics",
            "amount": 2450.00,
            "payment_method": "credit_card",
            "stripe_payment_intent_id": "pi_3Nxyz123",
            "settled_at": "2026-09-10T14:50:00Z"
        }
    },
    {
        "event_type": "shipment.updated",
        "description": "Triggered when EDI 856 ASN or carrier updates transit milestone or location.",
        "example_payload": {
            "po_number": "PO-AMZ-9021",
            "carrier": "FEDEX",
            "tracking_number": "794689234109",
            "status": "in_transit",
            "location": "FedEx Sort Hub, Memphis TN"
        }
    },
    {
        "event_type": "shipment.delivered",
        "description": "Triggered when vendor or parcel carrier confirms package delivery at client dock.",
        "example_payload": {
            "po_number": "PO-AMZ-9021",
            "carrier": "FEDEX",
            "tracking_number": "794689234109",
            "status": "delivered",
            "delivered_at": "2026-09-10T14:55:00Z"
        }
    },
    {
        "event_type": "license.provisioned",
        "description": "Triggered when an enterprise SaaS software license key is generated or renewed.",
        "example_payload": {
            "license_key": "LIC-TITAN-ENTERPRISE-01",
            "plan_tier": "enterprise",
            "seats": 50,
            "mrr": 1200.00,
            "client_name": "Nexus Aerospace"
        }
    },
    {
        "event_type": "restock.triggered",
        "description": "Triggered when the AI demand forecasting engine executes an automated replenishment order.",
        "example_payload": {
            "client_name": "Titan Industrial",
            "recommended_reorder_date": "2026-09-12",
            "burn_rate_daily": 45.20,
            "stockout_risk_score": 85
        }
    },
    {
        "event_type": "ping.test",
        "description": "Development diagnostic event dispatched during webhook setup verification.",
        "example_payload": {
            "message": "Webhook connectivity test ping from JsProject",
            "timestamp": "2026-09-10T14:50:00Z"
        }
    }
]

# ==============================================================================
# API Keys Endpoints
# ==============================================================================

@router.get("/keys", response_model=List[ApiKeyListItemResponse])
async def list_api_keys(
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(DEVELOPER_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """List all developer API keys provisioned for the organization."""
    _, org, _ = tenant_context
    stmt = select(ApiKey).where(ApiKey.organization_id == org.id).order_by(desc(ApiKey.created_at))
    res = await db.execute(stmt)
    keys = res.scalars().all()
    return [
        ApiKeyListItemResponse(
            id=k.id,
            key_name=k.key_name,
            key_prefix=k.key_prefix,
            scopes=k.scopes,
            rate_limit_per_minute=k.rate_limit_per_minute,
            is_active=k.is_active,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
            expires_at=k.expires_at
        )
        for k in keys
    ]

@router.post("/keys", response_model=ApiKeyCreatedResponse)
async def create_api_key(
    payload: ApiKeyCreateRequest,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(DEVELOPER_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate a new scoped API key.
    The raw secret key is returned only once upon creation.
    """
    current_user, org, role = tenant_context

    raw_token = f"jsp_live_{secrets.token_urlsafe(28)}"
    key_prefix = raw_token[:16]  # e.g., jsp_live_a1b2c3d4
    hashed_key = hashlib.sha256(raw_token.encode()).hexdigest()

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=payload.expires_in_days) if payload.expires_in_days else None

    api_key_rec = ApiKey(
        organization_id=org.id,
        key_name=payload.key_name,
        key_prefix=key_prefix,
        hashed_key=hashed_key,
        scopes=payload.scopes or ["*"],
        rate_limit_per_minute=payload.rate_limit_per_minute or 120,
        is_active=True,
        expires_at=expires_at,
        created_by_user_id=current_user.id
    )
    db.add(api_key_rec)

    await AuditService.log_event(
        db=db,
        org_id=org.id,
        action="developer.api_key_created",
        actor_type="user",
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=role,
        target_entity="api_key",
        status="success",
        payload={"key_name": payload.key_name, "key_prefix": key_prefix, "scopes": payload.scopes}
    )

    await db.commit()
    await db.refresh(api_key_rec)

    return ApiKeyCreatedResponse(
        id=api_key_rec.id,
        key_name=api_key_rec.key_name,
        key_prefix=key_prefix,
        api_key=raw_token,
        scopes=api_key_rec.scopes,
        rate_limit_per_minute=api_key_rec.rate_limit_per_minute,
        created_at=api_key_rec.created_at,
        expires_at=api_key_rec.expires_at
    )

@router.delete("/keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(DEVELOPER_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """Revoke an API key immediately."""
    current_user, org, role = tenant_context
    stmt = select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == org.id)
    res = await db.execute(stmt)
    key_rec = res.scalar_one_or_none()
    if not key_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found.")

    key_prefix = key_rec.key_prefix
    key_rec.is_active = False

    await AuditService.log_event(
        db=db,
        org_id=org.id,
        action="developer.api_key_revoked",
        actor_type="user",
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=role,
        target_entity="api_key",
        target_id=key_id,
        status="success",
        payload={"revoked_prefix": key_prefix}
    )

    await db.commit()
    return {"message": "API key revoked successfully.", "key_id": key_id, "id": key_id, "is_active": False}

# ==============================================================================
# Webhooks Endpoints
# ==============================================================================

@router.get("/webhooks", response_model=List[WebhookSubscriptionResponse])
async def list_webhooks(
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(DEVELOPER_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """List all outbound webhook subscriptions."""
    _, org, _ = tenant_context
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.organization_id == org.id
    ).order_by(desc(WebhookSubscription.created_at))
    res = await db.execute(stmt)
    subs = res.scalars().all()
    return [
        WebhookSubscriptionResponse(
            id=s.id,
            target_url=s.target_url,
            endpoint_url=s.target_url,
            description=s.description,
            events=s.events,
            secret_prefix=s.secret_key[:12] if s.secret_key else "",
            is_active=s.is_active,
            status="active" if s.is_active else "disabled",
            failure_count=s.failure_count,
            created_at=s.created_at
        )
        for s in subs
    ]

@router.post("/webhooks", response_model=WebhookSubscriptionCreatedResponse)
async def create_webhook(
    payload: WebhookSubscriptionCreateRequest,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(DEVELOPER_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """
    Subscribe a target HTTPS endpoint to event streams.
    Returns the HMAC signing secret once.
    """
    current_user, org, role = tenant_context

    secret_key = payload.secret_key.strip() if payload.secret_key else f"whsec_{secrets.token_hex(24)}"
    sub = WebhookSubscription(
        organization_id=org.id,
        target_url=payload.target_url.strip(),
        description=payload.description,
        events=payload.events or ["*"],
        secret_key=secret_key,
        is_active=True,
        failure_count=0
    )
    db.add(sub)

    await AuditService.log_event(
        db=db,
        org_id=org.id,
        action="developer.webhook_subscribed",
        actor_type="user",
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=role,
        target_entity="webhook_subscription",
        status="success",
        payload={"target_url": payload.target_url, "events": payload.events}
    )

    await db.commit()
    await db.refresh(sub)

    return WebhookSubscriptionCreatedResponse(
        id=sub.id,
        target_url=sub.target_url,
        endpoint_url=sub.target_url,
        description=sub.description,
        events=sub.events,
        secret_key=secret_key,
        secret_prefix=secret_key[:12],
        is_active=sub.is_active,
        status="active" if sub.is_active else "disabled",
        created_at=sub.created_at
    )

@router.patch("/webhooks/{sub_id}", response_model=WebhookSubscriptionResponse)
async def update_webhook(
    sub_id: str,
    payload: WebhookSubscriptionUpdateRequest,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(DEVELOPER_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """Update webhook target URL, subscribed events, or active status."""
    _, org, _ = tenant_context
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.id == sub_id,
        WebhookSubscription.organization_id == org.id
    )
    res = await db.execute(stmt)
    sub = res.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")

    if payload.target_url is not None:
        sub.target_url = payload.target_url.strip()
    if payload.description is not None:
        sub.description = payload.description
    if payload.events is not None:
        sub.events = payload.events
    if payload.is_active is not None:
        sub.is_active = payload.is_active
        if payload.is_active:
            sub.failure_count = 0  # Reset failure count when re-enabling

    db.add(sub)
    await db.commit()
    await db.refresh(sub)

    return WebhookSubscriptionResponse(
        id=sub.id,
        target_url=sub.target_url,
        endpoint_url=sub.target_url,
        description=sub.description,
        events=sub.events,
        secret_prefix=sub.secret_key[:12] if sub.secret_key else "",
        is_active=sub.is_active,
        status="active" if sub.is_active else "disabled",
        failure_count=sub.failure_count,
        created_at=sub.created_at
    )

@router.delete("/webhooks/{sub_id}")
async def delete_webhook(
    sub_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(DEVELOPER_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """Delete a webhook subscription."""
    current_user, org, role = tenant_context
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.id == sub_id,
        WebhookSubscription.organization_id == org.id
    )
    res = await db.execute(stmt)
    sub = res.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")

    target_url = sub.target_url
    await db.delete(sub)

    await AuditService.log_event(
        db=db,
        org_id=org.id,
        action="developer.webhook_deleted",
        actor_type="user",
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=role,
        target_entity="webhook_subscription",
        target_id=sub_id,
        status="success",
        payload={"target_url": target_url}
    )

    await db.commit()
    return {"message": "Webhook subscription deleted successfully.", "subscription_id": sub_id}

@router.get("/webhooks/{sub_id}/deliveries", response_model=List[WebhookDeliveryLogResponse])
async def list_webhook_deliveries(
    sub_id: str,
    limit: int = Query(25, ge=1, le=100),
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(DEVELOPER_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """View recent delivery attempts and responses for a webhook subscription."""
    _, org, _ = tenant_context
    stmt = select(WebhookDeliveryLog).where(
        WebhookDeliveryLog.subscription_id == sub_id,
        WebhookDeliveryLog.organization_id == org.id
    ).order_by(desc(WebhookDeliveryLog.delivered_at)).limit(limit)
    res = await db.execute(stmt)
    logs = res.scalars().all()
    return [
        WebhookDeliveryLogResponse(
            id=l.id,
            delivery_uuid=l.delivery_uuid,
            event_type=l.event_type,
            status=l.status,
            response_status_code=l.response_status_code,
            duration_ms=l.duration_ms,
            delivered_at=l.delivered_at,
            response_body_snippet=l.response_body[:200] if l.response_body else ""
        )
        for l in logs
    ]

@router.post("/webhooks/{sub_id}/ping", response_model=WebhookPingResponse)
async def ping_webhook(
    sub_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(DEVELOPER_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """Send an immediate test ping event to verify endpoint connectivity."""
    _, org, _ = tenant_context
    try:
        ping_res = await WebhookService.ping_subscription(sub_id, org.id, db)
        return ping_res
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error pinging webhook: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/events", response_model=List[EventCatalogItemResponse])
async def get_event_catalog():
    """Catalog of supported webhook event types and schemas."""
    return [EventCatalogItemResponse(**e) for e in SUPPORTED_EVENTS]
