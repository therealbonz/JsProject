from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization
from app.models.crm import SaaSLicense, SaaSExpansionProposal, ClientAccount, Company, Contact
from app.schemas.saas_license import (
    SaaSLicenseCreate, SaaSLicenseUpdate, SaaSLicenseResponse,
    SaaSTelemetryPingRequest,
    SaaSExpansionAuditResponse,
    SaaSRenewalScanResponse,
    SaaSCloudProvisionRequest, SaaSCloudProvisionResponse,
    SaaSOverviewMetrics
)
from app.services.saas_license_service import saas_license_service

router = APIRouter(prefix="/saas-licenses", tags=["SaaS License CRM"])

def map_license_response(lic: SaaSLicense) -> dict:
    now = datetime.now(timezone.utc)
    days_left = None
    if lic.renewal_date:
        ren = lic.renewal_date
        if ren.tzinfo is None:
            ren = ren.replace(tzinfo=timezone.utc)
        days_left = max(0, (ren - now).days)
    return {
        "id": lic.id,
        "organization_id": lic.organization_id,
        "client_id": lic.client_id,
        "company_id": lic.company_id,
        "primary_contact_id": lic.primary_contact_id,
        "company_name": lic.company.name if lic.company else None,
        "client_name": lic.client.account_name if lic.client else None,
        "contact_name": f"{lic.primary_contact.first_name} {lic.primary_contact.last_name}" if lic.primary_contact else None,
        "contact_email": lic.primary_contact.email if lic.primary_contact else None,
        "license_key": lic.license_key,
        "license_token": lic.license_token,
        "product_name": lic.product_name,
        "plan_tier": lic.plan_tier,
        "license_status": lic.license_status,
        "billing_interval": lic.billing_interval,
        "seat_unit_price": lic.seat_unit_price,
        "licensed_seats": lic.licensed_seats,
        "active_seats_used": lic.active_seats_used,
        "seat_utilization_pct": lic.seat_utilization_pct,
        "monthly_quota_units": lic.monthly_quota_units,
        "current_quota_used": lic.current_quota_used,
        "overage_allowed": lic.overage_allowed,
        "overage_unit_rate": lic.overage_unit_rate,
        "mrr": lic.mrr,
        "arr": lic.arr,
        "auto_renew": lic.auto_renew,
        "contract_start_date": lic.contract_start_date,
        "renewal_date": lic.renewal_date,
        "days_until_renewal": days_left,
        "last_telemetry_at": lic.last_telemetry_at,
        "health_score": lic.health_score,
        "churn_risk_level": lic.churn_risk_level,
        "health_rationale": lic.health_rationale,
        "features_enabled": lic.features_enabled or [],
        "notes": lic.notes,
        "created_at": lic.created_at,
        "updated_at": lic.updated_at
    }

@router.get("", response_model=List[SaaSLicenseResponse])
async def list_licenses(
    status_filter: Optional[str] = Query(None, alias="status"),
    plan_tier: Optional[str] = Query(None),
    churn_risk: Optional[str] = Query(None),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(SaaSLicense).options(
        selectinload(SaaSLicense.client),
        selectinload(SaaSLicense.company),
        selectinload(SaaSLicense.primary_contact)
    ).where(SaaSLicense.organization_id == org.id)

    if status_filter:
        stmt = stmt.where(SaaSLicense.license_status == status_filter)
    if plan_tier:
        stmt = stmt.where(SaaSLicense.plan_tier == plan_tier)
    if churn_risk:
        stmt = stmt.where(SaaSLicense.churn_risk_level == churn_risk)

    stmt = stmt.order_by(SaaSLicense.created_at.desc())
    res = await db.execute(stmt)
    licenses = res.scalars().all()
    return [map_license_response(l) for l in licenses]

@router.get("/metrics/overview", response_model=SaaSOverviewMetrics)
async def get_saas_metrics(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    return await saas_license_service.get_overview_metrics(db, org.id)

@router.post("", response_model=SaaSLicenseResponse, status_code=status.HTTP_201_CREATED)
async def provision_new_license(
    payload: SaaSLicenseCreate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    user, org, _ = tenant_context
    try:
        lic = await saas_license_service.provision_license(
            db=db,
            org=org,
            user=user,
            client_account_id=payload.client_id,
            plan_tier=payload.plan_tier or "pro",
            product_name=payload.product_name or "Enterprise AI Platform",
            billing_interval=payload.billing_interval or "annual",
            licensed_seats=payload.licensed_seats or 25,
            seat_unit_price=payload.seat_unit_price or 50.0,
            monthly_quota_units=payload.monthly_quota_units or 100000,
            overage_allowed=payload.overage_allowed if payload.overage_allowed is not None else True,
            overage_unit_rate=payload.overage_unit_rate or 0.05,
            auto_renew=payload.auto_renew if payload.auto_renew is not None else True,
            features_enabled=payload.features_enabled,
            notes=payload.notes
        )
        # Reload with relationships
        stmt = select(SaaSLicense).options(
            selectinload(SaaSLicense.client),
            selectinload(SaaSLicense.company),
            selectinload(SaaSLicense.primary_contact)
        ).where(SaaSLicense.id == lic.id)
        res = await db.execute(stmt)
        full_lic = res.scalar_one()
        return map_license_response(full_lic)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{license_id}", response_model=SaaSLicenseResponse)
async def get_license_detail(
    license_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(SaaSLicense).options(
        selectinload(SaaSLicense.client),
        selectinload(SaaSLicense.company),
        selectinload(SaaSLicense.primary_contact),
        selectinload(SaaSLicense.expansion_proposals)
    ).where(
        SaaSLicense.id == license_id,
        SaaSLicense.organization_id == org.id
    )
    res = await db.execute(stmt)
    lic = res.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SaaS License not found")
    return map_license_response(lic)

@router.patch("/{license_id}", response_model=SaaSLicenseResponse)
async def update_license(
    license_id: str,
    payload: SaaSLicenseUpdate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(SaaSLicense).options(
        selectinload(SaaSLicense.client),
        selectinload(SaaSLicense.company),
        selectinload(SaaSLicense.primary_contact)
    ).where(
        SaaSLicense.id == license_id,
        SaaSLicense.organization_id == org.id
    )
    res = await db.execute(stmt)
    lic = res.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SaaS License not found")

    update_data = payload.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lic, field, value)

    # Re-calculate MRR/ARR if seats or unit price changed
    if "licensed_seats" in update_data or "seat_unit_price" in update_data:
        lic.mrr = float(lic.licensed_seats * lic.seat_unit_price)
        lic.arr = float(lic.mrr * 12)
        if lic.licensed_seats > 0:
            lic.seat_utilization_pct = round((lic.active_seats_used / lic.licensed_seats) * 100, 1)

    await db.commit()
    await db.refresh(lic)
    return map_license_response(lic)

@router.post("/{license_id}/telemetry", response_model=SaaSLicenseResponse)
async def ingest_license_telemetry(
    license_id: str,
    payload: SaaSTelemetryPingRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(SaaSLicense).options(
        selectinload(SaaSLicense.client),
        selectinload(SaaSLicense.company),
        selectinload(SaaSLicense.primary_contact)
    ).where(
        SaaSLicense.id == license_id,
        SaaSLicense.organization_id == org.id
    )
    res = await db.execute(stmt)
    lic = res.scalar_one_or_none()
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SaaS License not found")

    updated = await saas_license_service.ingest_telemetry(
        db=db,
        license_id=lic.id,
        active_seats=payload.active_seats,
        quota_used=payload.quota_used,
        daily_active_users=payload.daily_active_users,
        api_calls_count=payload.api_calls_count
    )
    return map_license_response(updated)

@router.post("/expansion-audit", response_model=SaaSExpansionAuditResponse)
async def run_expansion_audit(
    requested_discount_pct: float = Query(0.0, ge=0.0, le=100.0),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    return await saas_license_service.run_expansion_audit(
        db=db,
        org=org,
        requested_discount_pct=requested_discount_pct
    )

@router.post("/renewal-radar", response_model=SaaSRenewalScanResponse)
async def run_renewal_radar(
    lookahead_days: int = Query(60, ge=1, le=365),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    return await saas_license_service.run_renewal_radar(
        db=db,
        org=org,
        lookahead_days=lookahead_days
    )

@router.post("/{license_id}/provision-cloud", response_model=SaaSCloudProvisionResponse)
async def provision_cloud_resources(
    license_id: str,
    payload: SaaSCloudProvisionRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    try:
        return await saas_license_service.provision_cloud_resources(
            db=db,
            org=org,
            license_id=license_id,
            cloud_provider=payload.cloud_provider or "amazon_aws",
            resource_spec=payload.resource_spec
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
