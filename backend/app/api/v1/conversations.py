from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization
from app.models.conversation import Conversation, Message
from app.schemas.ai import MessageResponse

router = APIRouter(prefix="/conversations", tags=["Conversations"])

@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context

    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.organization_id == org.id
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    msg_stmt = select(Message).where(
        Message.conversation_id == conv.id
    ).order_by(Message.created_at.asc())
    msg_res = await db.execute(msg_stmt)
    return msg_res.scalars().all()
