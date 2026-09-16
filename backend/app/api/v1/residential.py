import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
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
