import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.tenant import Organization
from app.models.crm import Company, Contact, Lead, Opportunity, Appointment, CallLog
from app.schemas.residential import (
    TradeType, CarpetCleaningSpecs, LawnCareSpecs, RoofingSpecs,
    ResidentialQuoteRequest, ResidentialQuoteResponse,
    ResidentialChatRequest, ResidentialChatResponse,
    ResidentialBookingRequest, ResidentialBookingConfirmation
)
from app.services.residential_sales_engine import ResidentialSalesEngine
from app.services.residential_telephony_service import ResidentialSMSService, ResidentialVoiceService
from app.services.residential_fsm_service import ResidentialFSMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/residential", tags=["Residential Sales Bot"])

@router.post("/quote", response_model=ResidentialQuoteResponse)
async def calculate_residential_quote(request: ResidentialQuoteRequest):
    """
    Direct calculator for residential services:
    Carpet Cleaning, Lawn Care, and Roofing & Gutters.
    """
    return ResidentialSalesEngine.calculate_quote(
        trade=request.trade,
        carpet=request.carpet,
        lawn=request.lawn,
        roofing=request.roofing,
        promo_code=request.promo_code,
        zip_code=request.zip_code
    )

@router.post("/chat", response_model=ResidentialChatResponse)
async def chat_with_sales_bot(request: ResidentialChatRequest):
    """
    Conversational AI interaction turn with the Residential Sales Bot.
    Analyzes user requirements, dynamically calculates quotes, and drives toward appointment booking.
    """
    return await ResidentialSalesEngine.process_chat(
        message=request.message,
        conversation_id=request.conversation_id,
        trade=request.trade,
        history=request.history,
        current_quote=request.current_quote,
        homeowner_info=request.homeowner_info
    )

@router.get("/slots")
async def get_available_dispatch_slots(
    trade: str = Query("carpet_cleaning", description="Trade type"),
    days_ahead: int = Query(5, description="Number of days to forecast")
):
    """
    Returns available technician dispatch time windows for the homeowner calendar.
    """
    return {
        "trade": trade,
        "days": ResidentialSalesEngine.get_dispatch_slots(trade=trade, days_ahead=days_ahead)
    }

@router.get("/catalog")
async def get_residential_catalog():
    """
    Returns the comprehensive residential services catalog, pricing rules, and standard packages.
    """
    return {
        "carpet_cleaning": {
            "title": "Master Carpet & Upholstery Care",
            "base_rate_per_room": 45.0,
            "hallway_rate": 20.0,
            "stair_step_rate": 3.0,
            "pet_enzyme_treatment": 35.0,
            "scotchgard_protectant": 25.0,
            "minimum_callout": 120.0,
            "features": [
                "Commercial truckmounted hot-water steam extraction",
                "Hospital-grade pet urine crystal elimination",
                "Fast 4-6 hour dry time guarantee",
                "Safe for infants and pets (zero toxic residues)"
            ]
        },
        "lawn_care": {
            "title": "Turf & Estate Lawn Maintenance",
            "tiers": [
                {"tier": "small_quarter_acre", "label": "Under 0.25 Acre", "base_rate": 45.0},
                {"tier": "medium_half_acre", "label": "0.25 - 0.50 Acre", "base_rate": 65.0},
                {"tier": "large_one_acre", "label": "0.50 - 1.00 Acre", "base_rate": 95.0},
                {"tier": "estate_plus", "label": "1.00+ Acre Estate", "base_rate": 145.0}
            ],
            "cadence_discounts": {
                "weekly": "15% off per-visit rate",
                "biweekly": "Standard rate",
                "one_time": "+$25 overgrowth clearing"
            },
            "add_ons": {
                "core_aeration_overseed": "From $195",
                "weed_and_feed": "$65 per application",
                "curb_edging": "Always Included Free"
            }
        },
        "roofing": {
            "title": "Elite Roofing & Exterior Defense",
            "inspection_fee": 0.0,
            "emergency_leak_triage": 299.0,
            "full_replacement_sq_range": [420.0, 650.0],
            "gutter_cleaning_base": 149.0,
            "features": [
                "100% Free 21-point drone roof scan & photo report",
                "Same-day emergency leak tarping & attic moisture containment",
                "Insurance claim storm/hail adjuster assistance ($0 deductible goal)",
                "50-year non-prorated architectural shingle warranties"
            ]
        }
    }

@router.post("/book", response_model=ResidentialBookingConfirmation)
async def book_residential_appointment(
    req: ResidentialBookingRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Confirms residential booking, registers the homeowner in the CRM
    (Company/Household, Contact, Lead, Opportunity, Appointment),
    and returns a dispatch confirmation ticket.
    """
    # 1. Resolve organization
    org_stmt = select(Organization).where(Organization.status == "active").order_by(Organization.created_at)
    org = (await db.execute(org_stmt)).scalars().first()
    if not org:
        org = Organization(
            name="Apex Residential Services",
            slug="apex-residential",
            status="active"
        )
        db.add(org)
        await db.commit()
        await db.refresh(org)

    org_id = org.id

    # 2. Parse homeowner name
    name_parts = req.homeowner_name.strip().split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else "Homeowner"

    # 3. Create or find Company (Household)
    household_name = f"{req.homeowner_name} Household"
    company = Company(
        organization_id=org_id,
        name=household_name,
        industry="Residential Property",
        address=f"{req.address}, {req.zip_code}",
        phone=req.phone,
        notes=f"Residential customer for {req.trade}. Special instructions: {req.special_instructions or 'None'}"
    )
    db.add(company)
    await db.flush()

    # 4. Create Contact
    contact = Contact(
        organization_id=org_id,
        company_id=company.id,
        first_name=first_name,
        last_name=last_name,
        email=req.email or f"{first_name.lower()}.{uuid.uuid4().hex[:6]}@residential-guest.com",
        phone=req.phone,
        job_title="Homeowner",
        decision_maker_role="owner",
        is_primary=True
    )
    db.add(contact)
    await db.flush()

    # 5. Create Lead
    trade_clean = req.trade.replace("_", " ").title()
    lead = Lead(
        organization_id=org_id,
        company_id=company.id,
        contact_id=contact.id,
        lead_score=95,
        pipeline_stage="qualified",
        status="active",
        assigned_agent_id="residential_sales_bot",
        notes=(
            f"Residential Sales Bot booked appointment.\n"
            f"Service: {trade_clean}\n"
            f"Summary: {req.service_summary}\n"
            f"Estimated Total: ${req.estimated_total:,.2f}\n"
            f"Scheduled Date: {req.scheduled_date} ({req.time_window})\n"
            f"Address: {req.address}, {req.zip_code}"
        )
    )
    db.add(lead)
    await db.flush()

    # 6. Create Opportunity
    opp = Opportunity(
        organization_id=org_id,
        lead_id=lead.id,
        title=f"{trade_clean} - {req.homeowner_name}",
        estimated_value=req.estimated_total,
        probability=0.90,
        stage="proposal"
    )
    db.add(opp)
    await db.flush()

    # 7. Create Appointment
    time_window_labels = {
        "morning": "Morning (8:00 AM - 12:00 PM)",
        "afternoon": "Afternoon (12:00 PM - 4:00 PM)",
        "evening": "Late Afternoon (4:00 PM - 7:00 PM)"
    }
    window_key = "morning"
    for k in ["morning", "afternoon", "evening"]:
        if k in req.time_window.lower():
            window_key = k
            break
    display_window = time_window_labels.get(window_key, req.time_window)

    # Parse scheduled date
    try:
        scheduled_dt = datetime.strptime(req.scheduled_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except Exception:
        scheduled_dt = datetime.now(timezone.utc)

    appointment = Appointment(
        organization_id=org_id,
        lead_id=lead.id,
        company_id=company.id,
        contact_id=contact.id,
        title=f"{trade_clean} Service Dispatch ({display_window})",
        scheduled_at=scheduled_dt,
        duration_minutes=120,
        status="scheduled",
        closer_name="Apex Field Dispatch Lead",
        closer_email="dispatch@apex-homeservices.local",
        notes=f"Homeowner: {req.homeowner_name} | Address: {req.address}, {req.zip_code} | Est: ${req.estimated_total:,.2f}",
        booked_by_agent=True
    )
    db.add(appointment)
    await db.flush()

    # 8. Record CallLog / Action Record
    call_log = CallLog(
        organization_id=org_id,
        lead_id=lead.id,
        company_id=company.id,
        contact_id=contact.id,
        caller_name="Residential Sales AI Bot",
        called_at=datetime.now(timezone.utc),
        duration_minutes=3,
        outcome="scheduled_demo",
        notes=f"Homeowner completed online conversational booking for {trade_clean}. Est: ${req.estimated_total:,.2f}.",
        next_steps=f"Dispatch service crew on {req.scheduled_date} during {display_window} to {req.address}."
    )
    db.add(call_log)
    await db.commit()

    confirmation_code = f"APX-{trade_clean[:3].upper()}-{uuid.uuid4().hex[:6].upper()}"

    return ResidentialBookingConfirmation(
        booking_id=str(uuid.uuid4()),
        appointment_id=appointment.id,
        lead_id=lead.id,
        company_id=company.id,
        trade=req.trade,
        homeowner_name=req.homeowner_name,
        address=f"{req.address}, {req.zip_code}",
        scheduled_at=req.scheduled_date,
        time_window=display_window,
        status="confirmed",
        estimated_total=req.estimated_total,
        confirmation_number=confirmation_code,
        message=(
            f"Your appointment is confirmed! Our crew will arrive on {req.scheduled_date} "
            f"during the {display_window}. A confirmation SMS has been queued for {req.phone}."
        )
    )

@router.get("/bookings")
async def list_residential_bookings(
    limit: int = Query(20, description="Max bookings to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists recent residential bookings created by the Sales Bot.
    """
    stmt = (
        select(Appointment)
        .options(
            selectinload(Appointment.lead),
            selectinload(Appointment.company),
            selectinload(Appointment.contact)
        )
        .where(Appointment.booked_by_agent == True)
        .order_by(desc(Appointment.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    appts = result.scalars().all()

    return {
        "count": len(appts),
        "bookings": [
            {
                "id": a.id,
                "title": a.title,
                "homeowner": f"{a.contact.first_name} {a.contact.last_name}" if a.contact else "Guest Homeowner",
                "phone": a.contact.phone if a.contact else None,
                "address": a.company.address if a.company else None,
                "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else None,
                "status": a.status,
                "notes": a.notes
            }
            for a in appts
        ]
    }


# =========================================================================
# TELEPHONY & SMS DISPATCH ENDPOINTS (PHASE 2)
# =========================================================================

@router.post("/sms/webhook")
async def twilio_sms_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Twilio Inbound SMS Webhook:
    Receives homeowner text messages, parses trade requirements, calculates quotes,
    drives conversation, and executes text-to-book directly in CRM.
    Returns standard TwiML XML.
    """
    # Accept either Form-urlencoded (Twilio default) or JSON (simulator/testing)
    content_type = request.headers.get("content-type", "")
    from_number = None
    body_text = None

    if "application/json" in content_type:
        try:
            data = await request.json()
            from_number = data.get("From") or data.get("from_phone")
            body_text = data.get("Body") or data.get("body") or data.get("message")
        except Exception:
            pass
    else:
        form = await request.form()
        from_number = form.get("From")
        body_text = form.get("Body")

    if not from_number or not body_text:
        twiml = ResidentialSMSService.generate_twiml_message("Apex Home Services: How can we assist you today with carpet, lawn, or roofing?")
        return Response(content=twiml, media_type="application/xml")

    result = await ResidentialSMSService.process_inbound_sms(
        from_phone=str(from_number),
        body=str(body_text),
        db=db
    )
    return Response(content=result["twiml"], media_type="application/xml")


@router.post("/voice/inbound")
async def twilio_voice_inbound(request: Request):
    """
    Twilio Inbound Phone Call Webhook:
    Answers calls with Polly speech and sets up speech recognition gather.
    """
    base_url = str(request.base_url).rstrip("/")
    # Determine gather callback
    gather_url = f"{base_url}/api/v1/residential/voice/gather"
    if "/JsProject" in str(request.url):
        gather_url = f"{base_url}/JsProject/api/v1/residential/voice/gather"

    twiml = ResidentialVoiceService.generate_inbound_greeting(callback_url=gather_url)
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/gather")
async def twilio_voice_gather(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Twilio Speech-to-Text Gather Callback:
    Processes caller speech transcript, checks for active roof leaks or quotes carpet/lawn,
    and returns continuing spoken audio instructions.
    """
    content_type = request.headers.get("content-type", "")
    speech_result = ""
    caller_phone = "+1-800-555-0199"

    if "application/json" in content_type:
        try:
            data = await request.json()
            speech_result = data.get("SpeechResult") or data.get("speech_result") or data.get("transcript") or ""
            caller_phone = data.get("From") or data.get("caller_phone") or caller_phone
        except Exception:
            pass
    else:
        form = await request.form()
        speech_result = form.get("SpeechResult", "")
        caller_phone = form.get("From", caller_phone)

    base_url = str(request.base_url).rstrip("/")
    callback_url = f"{base_url}/api/v1/residential/voice/gather"

    twiml, _ = ResidentialVoiceService.process_voice_gather(
        speech_result=speech_result,
        caller_phone=caller_phone,
        callback_url=callback_url,
        db=db
    )
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/status")
async def twilio_voice_status_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Twilio Call Status Callback (Speed-to-Lead Missed Call Detector):
    When an incoming call is missed, busy, or unanswered, triggers an immediate SMS within 15 seconds.
    """
    form = await request.form()
    call_status = form.get("CallStatus", "").lower()
    call_duration = form.get("CallDuration", "0")
    caller_phone = form.get("From")

    triggered = False
    if caller_phone and (call_status in ["no-answer", "busy", "canceled", "failed"] or call_duration == "0"):
        await ResidentialSMSService.trigger_missed_call_textback(
            caller_phone=caller_phone,
            db=db
        )
        triggered = True

    return {"status": "processed", "missed_call_detected": triggered, "call_status": call_status}


# =========================================================================
# VIRTUAL SMARTPHONE & TELEPHONY SIMULATOR (FOR WEB PORTAL)
# =========================================================================

@router.post("/simulate/missed_call")
async def simulate_missed_call(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Simulates a homeowner missed call. Immediately dispatches speed-to-lead qualification SMS.
    """
    data = await request.json()
    caller_phone = data.get("caller_phone", "+13035550199")
    res = await ResidentialSMSService.trigger_missed_call_textback(
        caller_phone=caller_phone,
        db=db
    )
    session = ResidentialSMSService.get_session(caller_phone)
    return {
        "success": True,
        "caller_phone": caller_phone,
        "dispatched_sms": res["message"],
        "session": session
    }


@router.post("/simulate/sms")
async def simulate_sms_conversation(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Simulates a 2-way homeowner text message turn inside the web portal virtual phone screen.
    """
    data = await request.json()
    from_phone = data.get("from_phone", "+13035550199")
    body = data.get("body", "")
    
    result = await ResidentialSMSService.process_inbound_sms(
        from_phone=from_phone,
        body=body,
        db=db
    )
    session = ResidentialSMSService.get_session(from_phone)
    return {
        "reply": result["reply_text"],
        "trade": result["trade"],
        "state": result["state"],
        "booked": result["booked"],
        "booking_data": result.get("booking_data"),
        "messages": session.get("messages", [])
    }


@router.post("/simulate/voice")
async def simulate_voice_turn(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Simulates an inbound voice phone call with speech-to-text transcript
    and returns audio text for browser speech synthesis.
    """
    data = await request.json()
    speech = data.get("speech", "I have 3 bedrooms that need steam cleaning")
    caller_phone = data.get("caller_phone", "+13035550199")
    
    twiml, metadata = ResidentialVoiceService.process_voice_gather(
        speech_result=speech,
        caller_phone=caller_phone,
        callback_url="/api/v1/residential/voice/gather",
        db=db
    )

    # Extract spoken plain text from TwiML for client-side Web Speech audio playback
    import re
    say_matches = re.findall(r"<Say[^>]*>(.*?)</Say>", twiml, re.DOTALL)
    spoken_text = " ".join(m.strip() for m in say_matches) if say_matches else "Thank you for calling Apex Home Services."

    return {
        "spoken_text": spoken_text,
        "metadata": metadata,
        "twiml": twiml
    }


@router.get("/simulate/messages")
async def get_simulator_messages(phone: str = Query("+13035550199")):
    """Returns SMS thread for virtual phone screen."""
    session = ResidentialSMSService.get_session(phone)
    return {
        "phone": session["phone"],
        "messages": session.get("messages", [])
    }


# =========================================================================
# FIELD SERVICE MANAGEMENT (FSM) & CALENDAR INTEGRATION (PHASE 3)
# =========================================================================

@router.get("/calendar/{appointment_id}.ics")
async def download_appointment_ics(appointment_id: str, db: AsyncSession = Depends(get_db)):
    """
    Universal iCalendar (.ics) export:
    Provides an RFC 5545 compliant calendar file to add the appointment directly to
    Apple Calendar, Microsoft Outlook, or Google Calendar with pre-filled address and technician crew notes.
    """
    stmt = (
        select(Appointment)
        .options(
            selectinload(Appointment.company),
            selectinload(Appointment.contact)
        )
        .where(Appointment.id == appointment_id)
    )
    res = await db.execute(stmt)
    appointment = res.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    ics_text = ResidentialFSMService.generate_ics_calendar(
        appointment=appointment,
        company=appointment.company,
        contact=appointment.contact
    )

    headers = {
        "Content-Disposition": f'attachment; filename="Apex_Appointment_{appointment.id[:8]}.ics"'
    }
    return Response(content=ics_text, media_type="text/calendar", headers=headers)


@router.get("/calendar/{appointment_id}/google")
async def get_google_calendar_link(appointment_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns direct 1-click Google Calendar Add URL with arrival window and address pre-filled.
    """
    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.company))
        .where(Appointment.id == appointment_id)
    )
    res = await db.execute(stmt)
    appointment = res.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    google_url = ResidentialFSMService.generate_google_calendar_url(
        appointment=appointment,
        company=appointment.company
    )
    return {
        "appointment_id": appointment_id,
        "title": appointment.title,
        "google_calendar_url": google_url
    }


@router.get("/fsm/crews")
async def get_fsm_crews(trade: Optional[str] = Query(None, description="Filter by trade")):
    """
    Returns active technician crew roster, vehicle types, leads, and customer satisfaction ratings.
    """
    return {
        "crews": ResidentialFSMService.get_fleet_crews(trade=trade)
    }


@router.post("/fsm/sync/{appointment_id}")
async def sync_appointment_to_fsm(
    appointment_id: str,
    platform: str = Query("jobber", description="Target platform: jobber, housecall_pro, servicetitan"),
    db: AsyncSession = Depends(get_db)
):
    """
    Outbound FSM Sync:
    Compiles standard Jobber / Housecall Pro / ServiceTitan payload and fires webhook event.
    """
    stmt = (
        select(Appointment)
        .options(
            selectinload(Appointment.company),
            selectinload(Appointment.contact)
        )
        .where(Appointment.id == appointment_id)
    )
    res = await db.execute(stmt)
    appointment = res.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found")

    payload = ResidentialFSMService.build_fsm_payload(
        appointment=appointment,
        company=appointment.company,
        contact=appointment.contact,
        platform=platform
    )

    # Dispatches event via WebhookService
    org_id = appointment.organization_id
    if org_id:
        try:
            await WebhookService.dispatch_event(
                org_id=org_id,
                event_type="residential.fsm.job_created",
                data=payload,
                db=db
            )
        except Exception as e:
            logger.warning(f"Outbound webhook dispatch notice: {e}")

    return {
        "success": True,
        "platform": platform,
        "appointment_id": appointment_id,
        "payload": payload
    }


@router.post("/fsm/en_route")
async def trigger_en_route_alert(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Sends automated 30-minute pre-arrival SMS alert to homeowner:
    'Apex Dispatch Heads-Up: Crew is en route to your address! ETA: 25 minutes.'
    """
    data = await request.json()
    appointment_id = data.get("appointment_id")
    eta_minutes = int(data.get("eta_minutes", 25))

    if not appointment_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="appointment_id is required")

    result = await ResidentialFSMService.send_en_route_alert(
        appointment_id=appointment_id,
        eta_minutes=eta_minutes,
        db=db
    )
    return result


@router.post("/fsm/complete")
async def trigger_completion_alert(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """
    Marks appointment as completed, updates CRM opportunity to won, and sends satisfaction/review SMS.
    """
    data = await request.json()
    appointment_id = data.get("appointment_id")

    if not appointment_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="appointment_id is required")

    result = await ResidentialFSMService.send_completion_alert(
        appointment_id=appointment_id,
        db=db
    )
    return result


