from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization, AIConfiguration
from app.models.crm import Lead, Company, Contact, Product
from app.models.conversation import Conversation, Message
from app.models.hitl import HumanAssistanceRequest, AuditLog
from app.schemas.ai import (
    LeadResearchResult, OutreachDraftResult, InboundReplyAnalysis,
    MessageResponse
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
        if analysis.intent == "interested":
            lead.pipeline_stage = "connected"
            lead.lead_score = min(100, lead.lead_score + 15)
        elif analysis.intent == "unsubscribe":
            lead.status = "dnc"
            lead.pipeline_stage = "lost"

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
