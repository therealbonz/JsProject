import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization
from app.models.crm import Lead
from app.services.voice_ai_service import VoiceAIService
from app.services.collateral_dispatch_service import CollateralDispatchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Voice AI & Collateral Dispatch"])

class PostalDispatchPayload(BaseModel):
    lead_id: str
    template_id: str = "executive_briefing_letter"
    recipient_name: Optional[str] = None
    recipient_title: Optional[str] = None
    to_address: Optional[Dict[str, str]] = None

class DigitalDispatchPayload(BaseModel):
    lead_id: str
    to_email: Optional[str] = None
    recipient_name: Optional[str] = None

class VoiceCallPayload(BaseModel):
    lead_id: str
    target_phone: Optional[str] = None
    caller_name: Optional[str] = "Voice AI Switchboard Pathfinder"

@router.get("/collateral/templates")
async def get_collateral_templates():
    """
    Returns available physical and digital marketing literature templates.
    """
    return {"templates": CollateralDispatchService.get_available_templates()}

@router.post("/collateral/dispatch-postal")
async def dispatch_postal_collateral(
    payload: PostalDispatchPayload,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Dispatches physical marketing literature (letter or postcard) via Lob.com API.
    """
    user, org, _ = tenant_context
    stmt = select(Lead).where(Lead.id == payload.lead_id)
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    result = await CollateralDispatchService.dispatch_postal_collateral(
        db=db,
        lead=lead,
        template_id=payload.template_id,
        recipient_name=payload.recipient_name,
        recipient_title=payload.recipient_title,
        to_address=payload.to_address,
        org=org
    )
    return result

@router.post("/collateral/dispatch-digital")
async def dispatch_digital_collateral(
    payload: DigitalDispatchPayload,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Dispatches digital whitepaper via SendGrid transactional email.
    """
    user, org, _ = tenant_context
    stmt = select(Lead).where(Lead.id == payload.lead_id)
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    result = await CollateralDispatchService.dispatch_digital_whitepaper(
        db=db,
        lead=lead,
        to_email=payload.to_email,
        recipient_name=payload.recipient_name,
        org=org
    )
    return result

@router.post("/voice/call")
async def initiate_voice_call(
    payload: VoiceCallPayload,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiates outbound Voice AI switchboard discovery call via Twilio.
    """
    user, org, _ = tenant_context
    stmt = select(Lead).where(Lead.id == payload.lead_id)
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    result = await VoiceAIService.initiate_discovery_call(
        db=db,
        lead=lead,
        target_phone=payload.target_phone,
        caller_name=payload.caller_name or "Voice AI Switchboard Pathfinder",
        org=org
    )
    return result

@router.post("/voice/twiml")
async def serve_voice_twiml(
    request: Request,
    company: str = "Enterprise Organization"
):
    """
    Twilio Voice webhook callback providing dynamic TwiML XML.
    """
    twiml = VoiceAIService.generate_switchboard_twiml(company_name=company)
    return Response(content=twiml, media_type="application/xml")

@router.post("/voice/status")
async def receive_voice_status_callback(request: Request):
    """
    Twilio status callback webhook recording call progression.
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    duration = form_data.get("CallDuration")
    logger.info(f"[TWILIO WEBHOOK STATUS] SID: {call_sid} | Status: {call_status} | Duration: {duration}s")
    return {"status": "acknowledged", "call_sid": call_sid, "call_status": call_status}
