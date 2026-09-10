import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_tenant, require_roles
from app.models.tenant import User, Organization
from app.schemas.financials import (
    ExecutiveOverviewResponse,
    FinancialReconciliationResponse,
    RepCommissionLeaderboardResponse,
    RepCommissionSummary,
    RepCommissionRateUpdateRequest
)
from app.services.financial_service import FinancialService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/executive", tags=["Executive Financials & Reconciliation"])

# Roles permitted to view executive financials
FINANCIAL_VIEW_ROLES = ["admin", "sales_manager", "billing_officer"]
COMMISSION_EDIT_ROLES = ["admin", "sales_manager"]

@router.get("/overview", response_model=ExecutiveOverviewResponse)
async def get_executive_overview(
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(FINANCIAL_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns executive-level SaaS and supply metrics: MRR, ARR, revenue collected, COGS, gross/net margins, and NRR.
    """
    current_user, org, role = tenant_context
    try:
        overview = await FinancialService.compute_executive_overview(org.id, db)
        return overview
    except Exception as e:
        logger.error(f"Error computing executive overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate executive analytics: {str(e)}"
        )

@router.get("/reconciliation", response_model=FinancialReconciliationResponse)
async def get_financial_reconciliation(
    start_date: Optional[datetime] = Query(None, description="Reconciliation start date (ISO 8601)"),
    end_date: Optional[datetime] = Query(None, description="Reconciliation end date (ISO 8601)"),
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(FINANCIAL_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a structured financial reconciliation statement matching client collections, supplier costs, and sales commissions.
    """
    current_user, org, role = tenant_context
    try:
        statement = await FinancialService.generate_reconciliation_statement(
            tenant_id=org.id,
            db=db,
            start_date=start_date,
            end_date=end_date
        )
        return statement
    except Exception as e:
        logger.error(f"Error generating reconciliation statement: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate financial reconciliation statement: {str(e)}"
        )

@router.get("/reconciliation/export")
async def export_reconciliation_statement(
    start_date: Optional[datetime] = Query(None, description="Reconciliation start date"),
    end_date: Optional[datetime] = Query(None, description="Reconciliation end date"),
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(FINANCIAL_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """
    Exports the reconciliation statement as an RFC 4180 CSV document for external accounting and reconciliation.
    """
    current_user, org, role = tenant_context
    try:
        statement = await FinancialService.generate_reconciliation_statement(
            tenant_id=org.id,
            db=db,
            start_date=start_date,
            end_date=end_date
        )
        csv_data = FinancialService.export_reconciliation_csv(statement)
        filename = f"financial_reconciliation_{org.slug}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Error exporting reconciliation CSV: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export reconciliation statement: {str(e)}"
        )

@router.get("/commissions", response_model=RepCommissionLeaderboardResponse)
async def get_rep_commissions(
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(FINANCIAL_VIEW_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns sales representative performance, deal volumes, and commission payout balances.
    """
    current_user, org, role = tenant_context
    try:
        return await FinancialService.compute_rep_commissions(org.id, db)
    except Exception as e:
        logger.error(f"Error fetching rep commissions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute sales commissions: {str(e)}"
        )

@router.patch("/commissions/{user_id}", response_model=RepCommissionSummary)
async def update_rep_commission_rate(
    user_id: str,
    payload: RepCommissionRateUpdateRequest,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(COMMISSION_EDIT_ROLES)),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates a sales representative's commission rate percentage.
    """
    current_user, org, role = tenant_context
    try:
        summary = await FinancialService.update_rep_commission_rate(
            tenant_id=org.id,
            user_id=user_id,
            new_rate=payload.commission_rate_pct,
            db=db,
            actor_email=current_user.email,
            actor_role=role
        )
        return summary
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Error updating rep commission rate: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update commission rate: {str(e)}"
        )
