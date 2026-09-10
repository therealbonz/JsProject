from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tenant import User, Organization
from app.api.deps import get_current_tenant
from app.services.replenishment_service import ReplenishmentService

router = APIRouter(tags=["Replenishments & Recurring Orders"])

class GenerateReplenishmentRequest(BaseModel):
    items_summary: Optional[str] = None
    amount: Optional[float] = None

class SnoozeReplenishmentRequest(BaseModel):
    snooze_days: Optional[int] = 14

@router.get("/crm/replenishments/due")
async def get_due_replenishments(
    threshold_days: int = 7,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all active client accounts with scheduled restocks due within threshold_days.
    """
    _, org, _ = tenant_context
    due = await ReplenishmentService.find_due_replenishments(
        db=db,
        org_id=org.id,
        threshold_days=threshold_days
    )
    return {
        "count": len(due),
        "threshold_days": threshold_days,
        "due_clients": due
    }

@router.post("/crm/replenishments/process-due")
async def process_due_replenishments(
    threshold_days: int = 7,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Evaluates all due client accounts and generates replenishment orders with Stripe payment links.
    """
    _, org, _ = tenant_context
    due = await ReplenishmentService.find_due_replenishments(
        db=db,
        org_id=org.id,
        threshold_days=threshold_days
    )

    generated = []
    for c in due:
        # If client doesn't already have an unpaid proposal, generate one
        if not c.get("pending_replenishment"):
            prop = await ReplenishmentService.generate_replenishment_proposal(
                db=db,
                org_id=org.id,
                client_id=c["client_id"]
            )
            generated.append(prop)

    return {
        "success": True,
        "scanned_count": len(due),
        "generated_count": len(generated),
        "proposals": generated
    }

@router.post("/crm/clients/{client_id}/generate-replenishment")
async def trigger_client_replenishment(
    client_id: str,
    payload: Optional[GenerateReplenishmentRequest] = None,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a replenishment proposal and Stripe payment link for a specific client account.
    """
    _, org, _ = tenant_context
    custom_items = payload.items_summary if payload else None
    custom_amount = payload.amount if payload else None

    try:
        proposal = await ReplenishmentService.generate_replenishment_proposal(
            db=db,
            org_id=org.id,
            client_id=client_id,
            custom_items=custom_items,
            custom_amount=custom_amount
        )
        return proposal
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/crm/clients/{client_id}/snooze-replenishment")
async def snooze_client_replenishment(
    client_id: str,
    payload: Optional[SnoozeReplenishmentRequest] = None,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Pushes client's next_reorder_date forward by snooze_days.
    """
    _, org, _ = tenant_context
    snooze_days = payload.snooze_days if payload and payload.snooze_days else 14
    try:
        res = await ReplenishmentService.snooze_replenishment(
            db=db,
            org_id=org.id,
            client_id=client_id,
            snooze_days=snooze_days
        )
        return res
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
