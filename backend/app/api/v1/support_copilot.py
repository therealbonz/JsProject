import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tenant import User, Organization
from app.api.deps import get_current_tenant, require_roles
from app.services.support_copilot_service import SupportCopilotService
from app.schemas.support_copilot import (
    CopilotChatRequest,
    CopilotChatResponse,
    CopilotMessageDTO,
    CopilotConversationSummary,
    CopilotConversationDetail,
    CopilotHumanReplyRequest,
    CopilotEscalateRequest
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support-copilot", tags=["AI Support Copilot & HITL"])

# ==============================================================================
# Customer Portal Facing Endpoints (Token-Authenticated)
# ==============================================================================

@router.post("/portal/{token}/chat", response_model=CopilotChatResponse)
async def chat_with_portal_copilot(
    token: str,
    payload: CopilotChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Customer portal chat message endpoint.
    Executes autonomous Copilot tool-use (order lookup, tracking, replenishment restock, billing, HITL escalation).
    """
    try:
        return await SupportCopilotService.process_portal_chat(
            db=db,
            portal_token=token,
            user_message=payload.message,
            conversation_id=payload.conversation_id
        )
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))
    except Exception as ex:
        logger.error(f"Error in support copilot chat: {ex}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Copilot failed to process message.")

@router.get("/portal/{token}/history", response_model=List[CopilotMessageDTO])
async def get_portal_chat_history(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves full chat message history for the active customer portal session.
    """
    try:
        return await SupportCopilotService.get_portal_chat_history(db, token)
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))

@router.post("/portal/{token}/escalate")
async def escalate_portal_session(
    token: str,
    payload: Optional[CopilotEscalateRequest] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Explicitly escalates the customer portal session to the assigned account manager.
    """
    try:
        reason = payload.reason if payload else "Customer requested human assistance"
        return await SupportCopilotService.escalate_portal_session(db, token, reason)
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))

# ==============================================================================
# CRM Admin & Rep Facing Endpoints (JWT-Authenticated)
# ==============================================================================

@router.get("/conversations", response_model=List[CopilotConversationSummary])
async def list_support_conversations(
    status: Optional[str] = Query(None, description="Filter by status: active, waiting_on_human, resolved"),
    limit: int = Query(50, ge=1, le=100),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists support copilot conversation threads for the active organization.
    """
    user, org, role = tenant_context
    return await SupportCopilotService.list_support_conversations(db, org.id, status, limit)

@router.get("/conversations/{conversation_id}", response_model=CopilotConversationDetail)
async def get_support_conversation_detail(
    conversation_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves detailed conversation messages, AI reasoning, and client account overview.
    """
    user, org, role = tenant_context
    detail = await SupportCopilotService.get_conversation_detail(db, conversation_id, org.id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return detail

@router.post("/conversations/{conversation_id}/reply", response_model=CopilotMessageDTO)
async def reply_as_human_rep(
    conversation_id: str,
    payload: CopilotHumanReplyRequest,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "sales_rep", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Takes over an escalated or active customer copilot conversation and replies as a human sales rep.
    """
    user, org, role = tenant_context
    try:
        return await SupportCopilotService.send_human_rep_reply(
            db=db,
            conversation_id=conversation_id,
            org_id=org.id,
            user=user,
            reply_text=payload.message,
            resolve_ticket=payload.resolve_ticket or False
        )
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))

@router.post("/conversations/{conversation_id}/resolve")
async def resolve_support_conversation(
    conversation_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "sales_rep", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Marks a support conversation and associated HITL tickets as resolved.
    """
    user, org, role = tenant_context
    success = await SupportCopilotService.resolve_conversation(db, conversation_id, org.id, user)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "success", "message": "Conversation marked as resolved."}
