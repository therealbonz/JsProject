import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization
from app.models.crm import ProspectCampaign, Lead
from app.services.campaign_dialer_service import CampaignDialerService
from app.schemas.dialer import CampaignDialRequest, CampaignDialResult, CampaignBatchProgress

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Campaign Dialer Bot"])


@router.post("/crm/campaigns/{campaign_id}/start", response_model=CampaignBatchProgress)
async def start_campaign_dialer(
    campaign_id: str,
    payload: Optional[CampaignDialRequest] = None,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Launches or resumes the autonomous outbound calling bot for a campaign.
    Pulls pending leads in batch and dials them with trade-specific scripts.
    """
    user, org, _ = tenant_context
    req = payload or CampaignDialRequest()

    try:
        progress = await CampaignDialerService.run_campaign_batch(
            campaign_id=campaign_id,
            organization_id=org.id,
            db=db,
            batch_size=req.batch_size,
            delay_seconds=req.delay_seconds,
            simulate=req.simulate,
            simulated_outcome=req.simulated_outcome
        )
        return progress
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/crm/campaigns/{campaign_id}/dial_next", response_model=CampaignDialResult)
async def dial_next_campaign_lead(
    campaign_id: str,
    payload: Optional[CampaignDialRequest] = None,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Dials the single next pending prospect in the campaign queue.
    Useful for step-by-step testing, previewing pitches, and single-lead calling.
    """
    user, org, _ = tenant_context
    req = payload or CampaignDialRequest()

    # Find next pending lead
    stmt = (
        select(Lead)
        .where(
            Lead.campaign_id == campaign_id,
            Lead.organization_id == org.id,
            Lead.pipeline_stage == "ready_contact",
            Lead.status == "active"
        )
        .order_by(Lead.created_at.asc())
        .limit(1)
    )
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending leads remaining in this campaign")

    result = await CampaignDialerService.dial_single_lead(
        lead_id=lead.id,
        campaign_id=campaign_id,
        db=db,
        simulate=req.simulate,
        simulated_outcome=req.simulated_outcome
    )
    return result


@router.post("/crm/campaigns/{campaign_id}/pause")
async def pause_campaign_dialer(
    campaign_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Pauses an active outbound calling campaign.
    """
    user, org, _ = tenant_context
    stmt = select(ProspectCampaign).where(
        ProspectCampaign.id == campaign_id,
        ProspectCampaign.organization_id == org.id
    )
    res = await db.execute(stmt)
    campaign = res.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    campaign.status = "paused"
    await db.commit()
    return {"status": "paused", "campaign_id": campaign_id, "message": f"Campaign '{campaign.name}' has been paused."}


@router.get("/crm/campaigns/{campaign_id}/progress", response_model=CampaignBatchProgress)
async def get_campaign_progress(
    campaign_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns real-time campaign progress, pending queue, connected calls, and booked appointments.
    """
    user, org, _ = tenant_context
    try:
        return await CampaignDialerService.get_campaign_progress(campaign_id, org.id, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/crm/campaigns/twiml/outbound")
async def serve_campaign_outbound_twiml(
    request: Request,
    trade: str = "carpet_cleaning",
    name: str = "Homeowner",
    address: Optional[str] = None
):
    """
    Twilio webhook callback delivering outbound campaign TwiML XML.
    """
    base_url = str(request.base_url).rstrip("/")
    callback_url = f"{base_url}/api/v1/crm/campaigns/twiml/gather"
    if "/JsProject" in str(request.url):
        callback_url = f"{base_url}/JsProject/api/v1/crm/campaigns/twiml/gather"

    twiml = CampaignDialerService.generate_outbound_twiml(
        trade=trade,
        homeowner_name=name,
        callback_url=callback_url,
        address=address
    )
    return Response(content=twiml, media_type="application/xml")


# =========================================================================
# PUBLIC / RESIDENTIAL PORTAL CONVENIENCE ENDPOINTS
# =========================================================================

@router.post("/residential/campaigns/{campaign_id}/dial_next", response_model=CampaignDialResult)
async def residential_dial_next_lead(
    campaign_id: str,
    payload: Optional[CampaignDialRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Portal convenience endpoint: Dials the next prospect in queue for a campaign without auth token.
    """
    camp_res = await db.execute(select(ProspectCampaign).where(ProspectCampaign.id == campaign_id))
    campaign = camp_res.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    stmt = (
        select(Lead)
        .where(
            Lead.campaign_id == campaign_id,
            Lead.pipeline_stage == "ready_contact",
            Lead.status == "active"
        )
        .order_by(Lead.created_at.asc())
        .limit(1)
    )
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending leads remaining in this campaign")

    req = payload or CampaignDialRequest()
    result = await CampaignDialerService.dial_single_lead(
        lead_id=lead.id,
        campaign_id=campaign_id,
        db=db,
        simulate=req.simulate,
        simulated_outcome=req.simulated_outcome
    )
    return result


@router.post("/residential/campaigns/{campaign_id}/start", response_model=CampaignBatchProgress)
async def residential_start_campaign(
    campaign_id: str,
    payload: Optional[CampaignDialRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Portal convenience endpoint: Batch dials pending leads for a campaign.
    """
    camp_res = await db.execute(select(ProspectCampaign).where(ProspectCampaign.id == campaign_id))
    campaign = camp_res.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    req = payload or CampaignDialRequest()
    progress = await CampaignDialerService.run_campaign_batch(
        campaign_id=campaign_id,
        organization_id=campaign.organization_id,
        db=db,
        batch_size=req.batch_size,
        delay_seconds=req.delay_seconds,
        simulate=req.simulate,
        simulated_outcome=req.simulated_outcome
    )
    return progress


@router.get("/residential/campaigns/{campaign_id}/progress", response_model=CampaignBatchProgress)
async def residential_get_campaign_progress(
    campaign_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Portal convenience endpoint: Returns campaign progress and conversion telemetry.
    """
    camp_res = await db.execute(select(ProspectCampaign).where(ProspectCampaign.id == campaign_id))
    campaign = camp_res.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    return await CampaignDialerService.get_campaign_progress(campaign_id, campaign.organization_id, db)
