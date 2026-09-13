import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, EmailStr
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization
from app.models.crm import Lead
from app.services.nurture_sequence_service import NurtureSequenceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Inbound Lead Nurturing"])

class InboundLeadCapturePayload(BaseModel):
    name: str
    email: str
    company_name: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = "landing_page_demo_request"
    industry: Optional[str] = None
    custom_notes: Optional[str] = None
    org_id: Optional[str] = None

class AdvanceCadencePayload(BaseModel):
    lead_id: Optional[str] = None
    force: bool = False

class PauseCadencePayload(BaseModel):
    event: str = "replied"
    notes: Optional[str] = None

@router.get("/nurture/cadence-definitions")
async def get_cadence_definitions():
    """
    Returns the 5-step autonomous inbound lead nurture roadmap.
    """
    return {"steps": NurtureSequenceService.get_cadence_definitions()}

@router.post("/nurture/inbound-capture")
async def capture_inbound_lead(
    payload: InboundLeadCapturePayload,
    db: AsyncSession = Depends(get_db)
):
    """
    Public or tenant-scoped inbound lead ingestion endpoint.
    Automatically enrolls prospect in 5-touchpoint cadence and dispatches Touchpoint 1.
    """
    org_id = payload.org_id
    if not org_id:
        res = await db.execute(select(Organization).limit(1))
        org = res.scalar_one_or_none()
        if not org:
            raise HTTPException(status_code=400, detail="No active organization available on platform.")
        org_id = org.id

    result = await NurtureSequenceService.ingest_inbound_lead(
        db=db,
        org_id=org_id,
        lead_name=payload.name,
        lead_email=payload.email,
        company_name=payload.company_name,
        phone=payload.phone,
        source=payload.source or "landing_page_demo_request",
        industry=payload.industry,
        custom_notes=payload.custom_notes
    )
    return result

@router.post("/nurture/advance")
async def advance_nurture_cadence(
    payload: AdvanceCadencePayload,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Advances an individual lead or scans and advances all due cadences in the organization.
    """
    user, org, _ = tenant_context

    if payload.lead_id:
        stmt = select(Lead).where(Lead.id == payload.lead_id, Lead.organization_id == org.id)
        res = await db.execute(stmt)
        lead = res.scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found in this organization")

        adv_res = await NurtureSequenceService.advance_lead_cadence(
            db=db,
            lead=lead,
            force=payload.force,
            org=org
        )
        return adv_res
    else:
        adv_res = await NurtureSequenceService.advance_all_due_cadences(
            db=db,
            org_id=org.id
        )
        return adv_res

@router.get("/nurture/lead/{lead_id}")
async def get_lead_nurture_status(
    lead_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves full cadence history and upcoming touchpoint details for a lead.
    """
    user, org, _ = tenant_context
    stmt = select(Lead).where(Lead.id == lead_id, Lead.organization_id == org.id)
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    return {
        "lead_id": lead.id,
        "nurture_status": lead.nurture_status,
        "nurture_step": lead.nurture_step,
        "next_nurture_at": lead.next_nurture_at.isoformat() if lead.next_nurture_at else None,
        "nurture_history": lead.nurture_history or []
    }

@router.post("/nurture/pause/{lead_id}")
async def pause_lead_nurture(
    lead_id: str,
    payload: PauseCadencePayload,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Pauses a lead's automated nurture cadence (e.g. when prospect replies or requests stop).
    """
    user, org, _ = tenant_context
    stmt = select(Lead).where(Lead.id == lead_id, Lead.organization_id == org.id)
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    result = await NurtureSequenceService.handle_prospect_reply(
        db=db,
        lead_id=lead.id,
        event=payload.event,
        notes=payload.notes
    )
    return result

@router.post("/nurture/resume/{lead_id}")
async def resume_lead_nurture(
    lead_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Resumes a paused nurture cadence for a lead.
    """
    user, org, _ = tenant_context
    stmt = select(Lead).where(Lead.id == lead_id, Lead.organization_id == org.id)
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.nurture_status = "active"
    lead.next_nurture_at = None
    await db.commit()
    await db.refresh(lead)

    return {
        "success": True,
        "lead_id": lead.id,
        "nurture_status": lead.nurture_status,
        "message": "Nurture sequence resumed."
    }

@router.get("/nurture/telemetry")
async def get_nurture_telemetry(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns organization-level inbound lead nurturing metrics and conversion statistics.
    """
    user, org, _ = tenant_context
    metrics = await NurtureSequenceService.get_cadence_telemetry(
        db=db,
        org_id=org.id
    )
    return metrics
