import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tenant import User, Organization
from app.api.deps import get_current_tenant
from app.schemas.crm import (
    DemandForecastResponse,
    DemandForecastOverviewStats,
    ApplyForecastCadenceRequest
)
from app.services.demand_forecast_service import DemandForecastService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Demand Forecasting & Safety Stock"])

@router.get("/crm/forecasting/overview", response_model=DemandForecastOverviewStats)
async def get_forecasting_overview(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns organization-wide demand intelligence summary (high-risk accounts count,
    projected 30-day restock volume, and average inventory consumption velocity).
    """
    _, org, _ = tenant_context
    stats = await DemandForecastService.get_overview_stats(db=db, org_id=org.id)
    return DemandForecastOverviewStats(**stats)

@router.get("/crm/clients/{client_id}/forecast", response_model=DemandForecastResponse)
async def get_client_demand_forecast(
    client_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves or generates the AI demand forecast and dynamic safety stock dossier for a client account.
    """
    _, org, _ = tenant_context
    try:
        forecast = await DemandForecastService.generate_forecast_for_client(
            db=db,
            org_id=org.id,
            client_id=client_id
        )
        return DemandForecastResponse(**forecast)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating client demand forecast: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/crm/clients/{client_id}/forecast/refresh", response_model=DemandForecastResponse)
async def refresh_client_demand_forecast(
    client_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Forces recalculation of a client's demand forecast and records a new historical forecast log.
    """
    _, org, _ = tenant_context
    try:
        forecast = await DemandForecastService.generate_forecast_for_client(
            db=db,
            org_id=org.id,
            client_id=client_id
        )
        return DemandForecastResponse(**forecast)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error refreshing demand forecast: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.post("/crm/clients/{client_id}/apply-forecast-cadence")
async def apply_forecast_cadence(
    client_id: str,
    payload: Optional[ApplyForecastCadenceRequest] = None,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Adopts the AI-recommended restock date and cadence on the client account.
    """
    _, org, _ = tenant_context
    apply_cadence = payload.apply_cadence_days if payload and payload.apply_cadence_days is not None else True
    apply_date = payload.apply_reorder_date if payload and payload.apply_reorder_date is not None else True

    try:
        result = await DemandForecastService.apply_forecast_to_cadence(
            db=db,
            org_id=org.id,
            client_id=client_id,
            apply_cadence_days=apply_cadence,
            apply_reorder_date=apply_date
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error applying forecast cadence: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
