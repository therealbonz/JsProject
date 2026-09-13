import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tenant import User, Organization
from app.api.deps import get_current_tenant
from app.services.pipeline_dag_engine import PipelineDagEngine, PIPELINE_STAGES
from app.services.workflow_engine import ENTERPRISE_TEMPLATES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline/dag", tags=["Autonomous Pipeline DAG"])

class ExecutePipelineRequest(BaseModel):
    lead_id: Optional[str] = None
    company_name: Optional[str] = None
    industry: Optional[str] = None
    target_value: float = Field(default=25000.0, ge=100.0)

class StepPipelineRequest(BaseModel):
    lead_id: str

@router.get("/template")
async def get_pipeline_dag_template():
    """
    Returns the visual 6-node DAG architecture schema and node coordinates for UI rendering.
    """
    dag_template = next((t for t in ENTERPRISE_TEMPLATES if t["id"] == "tpl_autonomous_6bot_pipeline"), None)
    return {
        "template": dag_template,
        "stages": PIPELINE_STAGES
    }

@router.post("/execute")
async def execute_full_pipeline_dag(
    payload: ExecutePipelineRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Executes the autonomous 6-stage sales bot pipeline sequentially end-to-end:
    1. Lead Dev (Enrichment & Scoring)
    2. DM Discovery & Literature Dispatch (Voice AI Switchboard Call & Collateral Mail)
    3. Cold Outreach SDR (1-to-1 Tailored Cadence)
    4. Appointment Setter (Calendar Negotiation & Demo Booking)
    5. Executive Sales Bot (Closing Dossier & $25k Commercial Proposal)
    6. Objection Closer (Concessions Applied & Deal Won)
    """
    user, org, _ = tenant_context

    result = await PipelineDagEngine.run_full_pipeline(
        db=db,
        org_id=org.id,
        lead_id=payload.lead_id,
        company_name=payload.company_name,
        industry=payload.industry,
        target_value=payload.target_value
    )
    return result

@router.post("/step")
async def step_pipeline_dag(
    payload: StepPipelineRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Advances the target lead by exactly one stage in the 6-stage DAG.
    """
    user, org, _ = tenant_context

    result = await PipelineDagEngine.step_lead_pipeline(
        db=db,
        org_id=org.id,
        lead_id=payload.lead_id
    )
    return result

@router.get("/status/{lead_id}")
async def get_lead_pipeline_status(
    lead_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns comprehensive execution status, current active bot, appointments, call logs,
    and stage history for the specified lead.
    """
    user, org, _ = tenant_context

    status_data = await PipelineDagEngine.get_pipeline_status(
        db=db,
        org_id=org.id,
        lead_id=lead_id
    )
    return status_data
