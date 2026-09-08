import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization, AIConfiguration
from app.models.crm import Lead, Company, Contact, Product, Appointment
from app.models.conversation import Conversation, Message
from app.models.hitl import HumanAssistanceRequest, AuditLog
from app.schemas.ai import (
    LeadResearchResult, OutreachDraftResult, InboundReplyAnalysis,
    MessageResponse, BusinessIntelligenceResult, AppointmentBookingRequest,
    AppointmentBookingResult, ExtractedDecisionMaker
)
from app.services.gemini_service import gemini_service

router = APIRouter(prefix="/agent", tags=["AI Sales Agent Engine"])

@router.post("/leads/{lead_id}/research", response_model=LeadResearchResult)
async def research_lead(
    lead_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context

    # 1. Fetch Lead
    stmt = select(Lead).options(
        selectinload(Lead.company),
        selectinload(Lead.contact)
    ).where(Lead.id == lead_id, Lead.organization_id == org.id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # 2. Fetch Organization Products
    prod_stmt = select(Product).where(Product.organization_id == org.id, Product.is_active == True)
    prod_res = await db.execute(prod_stmt)
    products = prod_res.scalars().all()
    catalog_summary = "\n".join([f"- {p.name} (${p.unit_price:.2f}): {p.description}" for p in products]) or "Commercial business supplies"

    # 3. Call Gemini
    contact_name = f"{lead.contact.first_name} {lead.contact.last_name}" if lead.contact else "Purchasing Lead"
    job_title = lead.contact.job_title if lead.contact else "Procurement"

    research_res = await gemini_service.research_and_score_lead(
        company_name=lead.company.name,
        domain=lead.company.domain,
        industry=lead.company.industry,
        contact_name=contact_name,
        job_title=job_title,
        product_summary=catalog_summary
    )

    # 4. Update Lead Record
    lead.lead_score = research_res.lead_score
    lead.pipeline_stage = "ready_contact"
    lead.research_summary = (
        f"Angle: {research_res.suggested_angle}\n"
        f"Overview: {research_res.company_overview}\n"
        f"Decision Maker: {research_res.decision_maker_analysis}\n"
        f"Pain Points: {', '.join(research_res.pain_points)}"
    )

    # 5. Audit Log
    audit = AuditLog(
        organization_id=org.id,
        actor_type="ai_agent",
        actor_id="gemini-sales-researcher",
        action="lead_researched_and_scored",
        target_entity="lead",
        target_id=lead.id,
        payload={
            "score": research_res.lead_score,
            "suggested_angle": research_res.suggested_angle,
            "confidence": research_res.confidence_score
        }
    )
    db.add(audit)
    await db.commit()

    return research_res

@router.post("/leads/{lead_id}/gather-intelligence", response_model=BusinessIntelligenceResult)
async def gather_lead_intelligence(
    lead_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Autonomously gathers organizational business intelligence, extracts corporate owners,
    C-level executives, and procurement decision-makers, and persists discovered contacts
    directly into the CRM under the company.
    """
    _, org, _ = tenant_context

    # 1. Fetch Lead with company and existing contacts
    stmt = select(Lead).options(
        selectinload(Lead.company).selectinload(Company.contacts),
        selectinload(Lead.contact)
    ).where(Lead.id == lead_id, Lead.organization_id == org.id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    company = lead.company

    # 2. Call Gemini BI discovery
    bi_res = await gemini_service.gather_business_intelligence(
        company_name=company.name,
        domain=company.domain,
        industry=company.industry,
        notes=company.notes or lead.notes
    )

    # 3. Auto-populate discovered decision makers into Contacts table if not already present
    existing_emails = {c.email.lower() for c in company.contacts if c.email}
    existing_names = {f"{c.first_name.lower()} {c.last_name.lower()}" for c in company.contacts}

    created_contacts_count = 0
    for dm in bi_res.key_decision_makers:
        full_name = f"{dm.first_name.lower()} {dm.last_name.lower()}"
        email_clean = dm.email.lower() if dm.email else None
        
        if (email_clean and email_clean in existing_emails) or full_name in existing_names:
            continue

        new_contact = Contact(
            organization_id=org.id,
            company_id=company.id,
            first_name=dm.first_name,
            last_name=dm.last_name,
            email=dm.email,
            phone=dm.phone,
            job_title=dm.job_title,
            decision_maker_role=dm.decision_maker_role,
            is_primary=False
        )
        db.add(new_contact)
        created_contacts_count += 1
        if email_clean:
            existing_emails.add(email_clean)
        existing_names.add(full_name)

    # 4. Save structured intelligence to Company research_data and Lead summary
    intel_data = bi_res.model_dump()
    research_dict = dict(company.research_data or {})
    research_dict["business_intelligence"] = intel_data
    company.research_data = research_dict

    dm_names = ", ".join([f"{d.first_name} {d.last_name} ({d.job_title})" for d in bi_res.key_decision_makers])
    lead.research_summary = (
        f"{lead.research_summary or ''}\n\n"
        f"--- Business Intelligence & Ownership ---\n"
        f"Ownership: {bi_res.ownership_structure}\n"
        f"Key Decision Makers: {dm_names}\n"
        f"Procurement Signals: {', '.join(bi_res.procurement_signals)}"
    ).strip()

    # 5. Audit Log
    audit = AuditLog(
        organization_id=org.id,
        actor_type="ai_agent",
        actor_id="gemini-bi-intelligence",
        action="business_intelligence_gathered",
        target_entity="lead",
        target_id=lead.id,
        payload={
            "company_name": company.name,
            "decision_makers_found": len(bi_res.key_decision_makers),
            "new_contacts_created": created_contacts_count
        }
    )
    db.add(audit)
    await db.commit()

    return bi_res

@router.post("/leads/{lead_id}/book-appointment", response_model=AppointmentBookingResult)
async def book_lead_appointment(
    lead_id: str,
    payload: Optional[AppointmentBookingRequest] = None,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Autonomous appointment setting: qualifies interest, schedules a calendar meeting
    with an assigned human closer/executive, generates an executive briefing dossier,
    and updates lead pipeline stage.
    """
    current_user, org, _ = tenant_context

    # 1. Fetch Lead with company, contact, conversations
    stmt = select(Lead).options(
        selectinload(Lead.company),
        selectinload(Lead.contact),
        selectinload(Lead.conversations).selectinload(Conversation.messages)
    ).where(Lead.id == lead_id, Lead.organization_id == org.id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # 2. Fetch Catalog
    prod_stmt = select(Product).where(Product.organization_id == org.id, Product.is_active == True)
    prod_res = await db.execute(prod_stmt)
    products = prod_res.scalars().all()
    catalog_str = "\n".join([f"- {p.name}: ${p.unit_price:.2f}" for p in products]) or "Commercial Supplies"

    # 3. Compile conversation history
    conv_history = ""
    target_conv = None
    if lead.conversations:
        target_conv = lead.conversations[0]
        conv_history = "\n".join([f"[{m.direction.upper()}] {m.body_text}" for m in target_conv.messages[-8:]])

    # 4. Determine scheduled time
    now_utc = datetime.now(timezone.utc)
    if payload and payload.scheduled_at:
        try:
            scheduled_dt = datetime.fromisoformat(payload.scheduled_at)
            if scheduled_dt.tzinfo is None:
                scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
        except Exception:
            scheduled_dt = now_utc + timedelta(days=1, hours=4)
    else:
        scheduled_dt = (now_utc + timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)

    closer_name = (payload.closer_name if payload and payload.closer_name else None) or current_user.full_name or "Senior Sales Executive"
    closer_email = (payload.closer_email if payload and payload.closer_email else None) or current_user.email
    meeting_url = (payload.meeting_url if payload and payload.meeting_url else None) or f"https://meet.google.com/agy-{str(uuid.uuid4())[:8]}"
    duration = (payload.duration_minutes if payload and payload.duration_minutes else 30)

    # 5. Generate Closer Briefing Dossier
    contact_name = f"{lead.contact.first_name} {lead.contact.last_name}" if lead.contact else "Executive Lead"
    job_title = lead.contact.job_title if lead.contact else "Decision Maker"

    briefing = await gemini_service.generate_closer_briefing(
        company_name=lead.company.name,
        contact_name=contact_name,
        job_title=job_title,
        conversation_history=conv_history,
        catalog_str=catalog_str,
        lead_score=lead.lead_score,
        research_summary=lead.research_summary
    )

    # 6. Create Appointment
    appointment = Appointment(
        organization_id=org.id,
        lead_id=lead.id,
        company_id=lead.company_id,
        contact_id=lead.contact_id,
        title=f"Executive Procurement Consultation - {lead.company.name}",
        scheduled_at=scheduled_dt,
        duration_minutes=duration,
        status="scheduled",
        meeting_url=meeting_url,
        closer_name=closer_name,
        closer_email=closer_email,
        executive_briefing=briefing,
        notes=payload.notes if payload else "Booked by AI Sales Agent following qualified interest.",
        booked_by_agent=True
    )
    db.add(appointment)

    # 7. Update Lead Pipeline
    lead.pipeline_stage = "qualified"
    lead.next_action_at = scheduled_dt
    lead.next_action_type = "scheduled_closer_call"

    # 8. Post confirmation message in conversation if thread exists
    if target_conv:
        conf_msg = Message(
            conversation_id=target_conv.id,
            sender_type="ai_agent",
            sender_name="Gemini Sales Agent",
            direction="outbound",
            subject="Confirmed: Executive Consultation & Pricing Review",
            body_text=(
                f"Hi {contact_name.split()[0]},\n\n"
                f"Great news! Your consultation with {closer_name} is confirmed for "
                f"{scheduled_dt.strftime('%A, %B %d at %I:%M %p UTC')}.\n\n"
                f"Meeting Link: {meeting_url}\n\n"
                f"We look forward to reviewing your supply requirements and presenting our consolidated wholesale pricing proposal."
            ),
            ai_reasoning={
                "action": "appointment_booked",
                "closer_name": closer_name,
                "scheduled_at": scheduled_dt.isoformat()
            },
            ai_confidence=0.98
        )
        db.add(conf_msg)

    # 9. Audit Log
    audit = AuditLog(
        organization_id=org.id,
        actor_type="ai_agent",
        actor_id="gemini-closer-orchestrator",
        action="appointment_booked_for_closer",
        target_entity="appointment",
        target_id=appointment.id,
        payload={
            "lead_id": lead.id,
            "closer_name": closer_name,
            "scheduled_at": scheduled_dt.isoformat(),
            "meeting_url": meeting_url
        }
    )
    db.add(audit)
    await db.commit()

    return AppointmentBookingResult(
        appointment_id=appointment.id,
        lead_id=lead.id,
        company_name=lead.company.name,
        contact_name=contact_name,
        scheduled_at=scheduled_dt.isoformat(),
        duration_minutes=duration,
        closer_name=closer_name,
        closer_email=closer_email,
        meeting_url=meeting_url,
        executive_briefing=briefing,
        status="scheduled"
    )

@router.post("/leads/{lead_id}/draft-outreach", response_model=OutreachDraftResult)
async def draft_outreach(
    lead_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context

    # 1. Fetch Lead
    stmt = select(Lead).options(
        selectinload(Lead.company),
        selectinload(Lead.contact)
    ).where(Lead.id == lead_id, Lead.organization_id == org.id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # 2. Fetch AI Config
    cfg_stmt = select(AIConfiguration).where(AIConfiguration.organization_id == org.id)
    cfg_res = await db.execute(cfg_stmt)
    ai_cfg = cfg_res.scalar_one_or_none()

    # 3. Fetch Catalog
    prod_stmt = select(Product).where(Product.organization_id == org.id, Product.is_active == True)
    prod_res = await db.execute(prod_stmt)
    products = prod_res.scalars().all()
    catalog_str = "\n".join([f"- {p.name} (SKU: {p.sku}): ${p.unit_price:.2f}. Min allowed: ${p.min_allowed_price:.2f}" for p in products])

    contact_name = f"{lead.contact.first_name} {lead.contact.last_name}" if lead.contact else "Valued Contact"
    job_title = lead.contact.job_title if lead.contact else "Purchasing"

    draft = await gemini_service.generate_outreach_email(
        company_name=lead.company.name,
        contact_name=contact_name,
        job_title=job_title,
        product_catalog_str=catalog_str,
        company_profile=(ai_cfg.company_description if ai_cfg else "Commercial B2B Supply Solutions"),
        tone=(ai_cfg.tone_of_voice if ai_cfg else "professional and consultative")
    )

    return draft

@router.post("/conversations/{conversation_id}/send-message", response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    subject: Optional[str] = None,
    body_text: str = "",
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    current_user, org, _ = tenant_context

    stmt = select(Conversation).where(
        ((Conversation.id == conversation_id) | (Conversation.lead_id == conversation_id)),
        Conversation.organization_id == org.id
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    message = Message(
        conversation_id=conv.id,
        sender_type="human_rep",
        sender_name=current_user.full_name,
        direction="outbound",
        subject=subject or "Follow-up",
        body_text=body_text,
        ai_reasoning={"sent_by_user_id": current_user.id}
    )
    db.add(message)

    # Update lead stage to contacted if new
    lead_stmt = select(Lead).where(Lead.id == conv.lead_id)
    lead_res = await db.execute(lead_stmt)
    lead = lead_res.scalar_one_or_none()
    if lead and lead.pipeline_stage in ["new", "ready_contact"]:
        lead.pipeline_stage = "contacted"
        lead.last_contacted_at = datetime.now(timezone.utc)
        lead.next_action_at = datetime.now(timezone.utc) + timedelta(days=3)
        lead.next_action_type = "automated_followup_check"

    await db.commit()
    await db.refresh(message)
    return message

@router.post("/conversations/{conversation_id}/inbound-simulate", response_model=InboundReplyAnalysis)
async def simulate_inbound_reply(
    conversation_id: str,
    incoming_text: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Simulates or processes an inbound message from a lead.
    Passes message to Gemini for intent/sentiment analysis and policy guardrail checks.
    Automatically triggers a HumanAssistanceRequest (HAR) if discount exceeds limit or sentiment is hostile.
    """
    _, org, _ = tenant_context

    stmt = select(Conversation).options(
        selectinload(Conversation.messages)
    ).where(
        ((Conversation.id == conversation_id) | (Conversation.lead_id == conversation_id)),
        Conversation.organization_id == org.id
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Fetch AI Config
    cfg_stmt = select(AIConfiguration).where(AIConfiguration.organization_id == org.id)
    cfg_res = await db.execute(cfg_stmt)
    ai_cfg = cfg_res.scalar_one_or_none()
    max_discount = ai_cfg.max_discount_pct if ai_cfg else 10.0

    # Fetch Catalog
    prod_stmt = select(Product).where(Product.organization_id == org.id, Product.is_active == True)
    prod_res = await db.execute(prod_stmt)
    products = prod_res.scalars().all()
    catalog_str = "\n".join([f"- {p.name}: ${p.unit_price:.2f}" for p in products])

    # History summary
    history_str = "\n".join([f"[{m.direction.upper()}] {m.body_text}" for m in conv.messages[-5:]])

    # Record inbound message
    inbound_msg = Message(
        conversation_id=conv.id,
        sender_type="lead",
        direction="inbound",
        subject="Re: Supplies procurement",
        body_text=incoming_text,
        ai_reasoning={}
    )
    db.add(inbound_msg)
    await db.flush()

    # Call Gemini analysis
    analysis = await gemini_service.analyze_inbound_reply(
        conversation_history=history_str,
        inbound_message=incoming_text,
        max_discount_pct=max_discount,
        product_catalog_str=catalog_str,
        ai_guidelines=ai_cfg.sales_guidelines if ai_cfg else None
    )

    conv.sentiment = analysis.sentiment
    conv.ai_summary = analysis.summary

    # Update Lead Stage
    lead_stmt = select(Lead).where(Lead.id == conv.lead_id)
    lead_res = await db.execute(lead_stmt)
    lead = lead_res.scalar_one_or_none()

    if lead:
        if analysis.intent in ["interested", "appointment_request"] or analysis.appointment_requested:
            lead.pipeline_stage = "connected"
            lead.lead_score = min(100, lead.lead_score + (25 if analysis.appointment_requested else 15))
            if analysis.appointment_requested:
                lead.next_action_type = "schedule_closer_meeting"
        elif analysis.intent == "gatekeeper_referral":
            lead.pipeline_stage = "connected"
            lead.lead_score = min(100, lead.lead_score + 10)
        elif analysis.intent == "unsubscribe":
            lead.status = "dnc"
            lead.pipeline_stage = "lost"

        # Auto-create referred decision-maker contact from gatekeeper
        if analysis.referred_contact and lead.company_id:
            ref = analysis.referred_contact
            c_check = select(Contact).where(
                Contact.company_id == lead.company_id,
                Contact.organization_id == org.id,
                (Contact.email == ref.email) if ref.email else (Contact.first_name == ref.first_name)
            )
            c_res = await db.execute(c_check)
            if not c_res.scalar_one_or_none():
                new_c = Contact(
                    organization_id=org.id,
                    company_id=lead.company_id,
                    first_name=ref.first_name,
                    last_name=ref.last_name,
                    email=ref.email,
                    phone=ref.phone,
                    job_title=ref.job_title,
                    decision_maker_role=ref.decision_maker_role,
                    is_primary=False
                )
                db.add(new_c)
                audit_ref = AuditLog(
                    organization_id=org.id,
                    actor_type="ai_agent",
                    actor_id="gemini-inbound-supervisor",
                    action="gatekeeper_referred_contact_created",
                    target_entity="contact",
                    target_id=new_c.id,
                    payload={
                        "referred_name": f"{ref.first_name} {ref.last_name}",
                        "job_title": ref.job_title,
                        "email": ref.email
                    }
                )
                db.add(audit_ref)

    # Human-in-the-Loop Check
    if analysis.requires_hitl:
        conv.status = "waiting_on_human"

        suggested_options = [
            f"Approve requested exception ({analysis.detected_discount_request}% discount)" if analysis.detected_discount_request else "Approve AI suggested response",
            f"Counter with maximum authorized discount ({max_discount}%)",
            "Take over conversation manually and reply directly"
        ]

        har = HumanAssistanceRequest(
            organization_id=org.id,
            conversation_id=conv.id,
            lead_id=conv.lead_id,
            trigger_reason="policy_discount_exceeded" if analysis.detected_discount_request else "escalation_required",
            situation_summary=analysis.hitl_reason or analysis.summary,
            suggested_options=suggested_options,
            ai_recommendation=analysis.suggested_reply,
            confidence_score=analysis.confidence_score,
            status="pending"
        )
        db.add(har)

        # Audit Log
        audit = AuditLog(
            organization_id=org.id,
            actor_type="ai_agent",
            actor_id="gemini-policy-supervisor",
            action="hitl_request_created",
            target_entity="human_assistance_request",
            target_id=har.id,
            payload={"reason": analysis.hitl_reason, "lead_id": conv.lead_id}
        )
        db.add(audit)

    else:
        # If no HITL required, AI can auto-reply or queue response
        if analysis.suggested_reply:
            ai_reply = Message(
                conversation_id=conv.id,
                sender_type="ai_agent",
                sender_name="Gemini Sales Agent",
                direction="outbound",
                subject="Re: Supplies procurement",
                body_text=analysis.suggested_reply,
                ai_reasoning={
                    "intent": analysis.intent,
                    "confidence": analysis.confidence_score,
                    "auto_sent": True
                },
                ai_confidence=analysis.confidence_score
            )
            db.add(ai_reply)

    await db.commit()
    return analysis
