from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization
from app.models.hitl import HumanAssistanceRequest, AuditLog
from app.models.conversation import Conversation, Message
from app.schemas.hitl import HARActionRequest, HARResponse, AuditLogResponse

router = APIRouter(prefix="/hitl", tags=["Human-in-the-Loop & Auditing"])

@router.get("/requests", response_model=List[HARResponse])
async def list_hitl_requests(
    status_filter: Optional[str] = Query("pending"),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(HumanAssistanceRequest).where(
        HumanAssistanceRequest.organization_id == org.id
    )
    if status_filter:
        stmt = stmt.where(HumanAssistanceRequest.status == status_filter)
    
    stmt = stmt.order_by(HumanAssistanceRequest.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/requests/{request_id}/action", response_model=HARResponse)
async def resolve_hitl_request(
    request_id: str,
    payload: HARActionRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    current_user, org, _ = tenant_context

    stmt = select(HumanAssistanceRequest).where(
        HumanAssistanceRequest.id == request_id,
        HumanAssistanceRequest.organization_id == org.id
    )
    result = await db.execute(stmt)
    har = result.scalar_one_or_none()

    if not har:
        raise HTTPException(status_code=404, detail="Assistance request not found")

    conv_stmt = select(Conversation).where(Conversation.id == har.conversation_id)
    conv_res = await db.execute(conv_stmt)
    conv = conv_res.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    har.reviewed_by_user_id = current_user.id
    har.reviewer_instructions = payload.instructions
    har.resolved_at = now

    if payload.action == "approve":
        har.status = "approved"
        if conv:
            conv.status = "active"
            # Send AI recommendation or custom reply
            reply_text = payload.custom_reply or har.ai_recommendation or "Approved by management."
            msg = Message(
                conversation_id=conv.id,
                sender_type="ai_agent",
                sender_name=f"Sales Team (Approved by {current_user.full_name})",
                direction="outbound",
                subject="Update on your proposal request",
                body_text=reply_text,
                ai_reasoning={"human_approved_by": current_user.id}
            )
            db.add(msg)

    elif payload.action == "reject":
        har.status = "rejected"
        if conv:
            conv.status = "active"
            msg = Message(
                conversation_id=conv.id,
                sender_type="ai_agent",
                sender_name="Sales Team",
                direction="outbound",
                subject="Pricing clarification",
                body_text=payload.custom_reply or "We appreciate your request, however we are unable to provide an additional discount on this tier.",
                ai_reasoning={"human_rejected_by": current_user.id}
            )
            db.add(msg)

    elif payload.action == "take_over":
        har.status = "taken_over"
        if conv:
            conv.status = "human_managed"
            if payload.custom_reply:
                msg = Message(
                    conversation_id=conv.id,
                    sender_type="human_rep",
                    sender_name=current_user.full_name,
                    direction="outbound",
                    subject="Direct response from Account Manager",
                    body_text=payload.custom_reply,
                    ai_reasoning={"manual_takeover_by": current_user.id}
                )
                db.add(msg)

    # Log action to audit
    audit = AuditLog(
        organization_id=org.id,
        actor_type="human_rep",
        actor_id=current_user.id,
        action=f"hitl_{payload.action}",
        target_entity="human_assistance_request",
        target_id=har.id,
        payload={"action": payload.action, "instructions": payload.instructions}
    )
    db.add(audit)

    await db.commit()
    await db.refresh(har)
    return har

@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    limit: int = Query(50, le=200),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(AuditLog).where(
        AuditLog.organization_id == org.id
    ).order_by(AuditLog.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()
