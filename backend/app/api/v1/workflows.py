import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.database import get_db
from app.models.tenant import User, Organization
from app.models.workflow import Workflow, WorkflowExecution
from app.api.deps import get_current_tenant, require_roles
from app.services.workflow_engine import WorkflowEngineService
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowSummary,
    WorkflowTestRunRequest,
    WorkflowTestRunResponse,
    WorkflowStepLog,
    WorkflowExecutionResponse,
    WorkflowExecutionDetail,
    WorkflowTemplateResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["Visual Workflow Automation Canvas"])

@router.get("/templates", response_model=List[WorkflowTemplateResponse])
async def list_workflow_templates(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant)
):
    """
    Returns curated pre-built enterprise workflow templates.
    """
    return WorkflowEngineService.list_templates()

@router.post("/templates/{template_id}/instantiate", response_model=WorkflowResponse)
async def instantiate_workflow_template(
    template_id: str,
    custom_name: Optional[str] = Query(None, description="Optional custom name for instantiated workflow"),
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "sales_manager", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    1-click clones an enterprise template recipe into the organization's active workflows.
    """
    user, org, role = tenant_context
    try:
        wf = await WorkflowEngineService.instantiate_template(db, org.id, template_id, custom_name)
        return wf
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))

@router.get("", response_model=List[WorkflowSummary])
async def list_workflows(
    status_filter: Optional[str] = Query(None, alias="status"),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists all workflows created within the active tenant organization.
    """
    user, org, role = tenant_context
    stmt = select(Workflow).where(Workflow.organization_id == org.id)
    if status_filter:
        stmt = stmt.where(Workflow.status == status_filter)
    stmt = stmt.order_by(Workflow.created_at.desc())
    res = await db.execute(stmt)
    workflows = res.scalars().all()

    summaries = []
    for wf in workflows:
        nodes = (wf.canvas_data or {}).get("nodes", [])
        total = wf.total_runs or 0
        success = wf.successful_runs or 0
        rate = round((success / total * 100.0), 1) if total > 0 else 100.0

        summaries.append(WorkflowSummary(
            id=wf.id,
            organization_id=wf.organization_id,
            name=wf.name,
            description=wf.description,
            trigger_type=wf.trigger_type,
            status=wf.status,
            is_active=wf.is_active,
            version=wf.version,
            node_count=len(nodes) or len(wf.steps or []),
            total_runs=total,
            successful_runs=success,
            failed_runs=wf.failed_runs or 0,
            success_rate_pct=rate,
            last_run_at=wf.last_run_at,
            created_at=wf.created_at
        ))
    return summaries

@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    payload: WorkflowCreate,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "sales_manager", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Creates a new custom visual automation workflow.
    """
    user, org, role = tenant_context
    wf = Workflow(
        organization_id=org.id,
        name=payload.name,
        description=payload.description,
        trigger_type=payload.trigger_type,
        trigger_config=payload.trigger_config or {},
        status=payload.status or "active",
        is_active=payload.is_active if payload.is_active is not None else True,
        version=1,
        canvas_data=payload.canvas_data or {},
        steps=payload.steps or []
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return wf

@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves complete visual canvas layout and step definitions for a workflow.
    """
    user, org, role = tenant_context
    stmt = select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == org.id)
    wf = (await db.execute(stmt)).scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return wf

@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: str,
    payload: WorkflowUpdate,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "sales_manager", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates workflow metadata, visual canvas coordinates, and executable steps.
    """
    user, org, role = tenant_context
    stmt = select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == org.id)
    wf = (await db.execute(stmt)).scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    if payload.name is not None:
        wf.name = payload.name
    if payload.description is not None:
        wf.description = payload.description
    if payload.trigger_type is not None:
        wf.trigger_type = payload.trigger_type
    if payload.trigger_config is not None:
        wf.trigger_config = payload.trigger_config
    if payload.status is not None:
        wf.status = payload.status
    if payload.is_active is not None:
        wf.is_active = payload.is_active
    if payload.canvas_data is not None:
        wf.canvas_data = payload.canvas_data
    if payload.steps is not None:
        wf.steps = payload.steps
    wf.version += 1

    await db.commit()
    await db.refresh(wf)
    return wf

@router.delete("/{workflow_id}", status_code=status.HTTP_200_OK)
async def delete_workflow(
    workflow_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Permanently deletes a workflow and associated run records.
    """
    user, org, role = tenant_context
    stmt = select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == org.id)
    wf = (await db.execute(stmt)).scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    await db.delete(wf)
    await db.commit()
    return {"status": "deleted", "workflow_id": workflow_id}

@router.post("/{workflow_id}/toggle", response_model=WorkflowResponse)
async def toggle_workflow_status(
    workflow_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "sales_manager", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggles workflow between active and paused states.
    """
    user, org, role = tenant_context
    stmt = select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == org.id)
    wf = (await db.execute(stmt)).scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    wf.is_active = not wf.is_active
    wf.status = "active" if wf.is_active else "paused"
    await db.commit()
    await db.refresh(wf)
    return wf

@router.post("/{workflow_id}/test", response_model=WorkflowTestRunResponse)
async def test_run_workflow(
    workflow_id: str,
    payload: WorkflowTestRunRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Performs a live dry-run simulation of the workflow with test payload,
    returning step-by-step telemetry, conditions evaluation, and AI agent output.
    """
    user, org, role = tenant_context
    stmt = select(Workflow).where(Workflow.id == workflow_id, Workflow.organization_id == org.id)
    wf = (await db.execute(stmt)).scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")

    test_payload = payload.trigger_payload or {
        "lead_id": "test-lead-001",
        "company_name": "Acme Industries",
        "estimated_value": 15000,
        "sentiment": "neutral",
        "stockout_risk_score": 85,
        "amount": 2500,
        "customer_email": "procurement@acme.example"
    }

    execution = await WorkflowEngineService.execute_workflow(
        db=db,
        workflow=wf,
        trigger_payload=test_payload,
        is_dry_run=True
    )

    step_logs = [
        WorkflowStepLog(
            step_id=s.get("step_id", ""),
            node_type=s.get("node_type", "action"),
            label=s.get("label", "Step"),
            status=s.get("status", "success"),
            duration_ms=s.get("duration_ms", 0.0),
            input=s.get("input"),
            output=s.get("output"),
            error=s.get("error")
        )
        for s in (execution.step_logs or [])
    ]

    return WorkflowTestRunResponse(
        workflow_id=wf.id,
        status=execution.status,
        execution_time_ms=execution.execution_time_ms,
        steps_executed=len(step_logs),
        step_logs=step_logs,
        error_message=execution.error_message
    )

@router.get("/{workflow_id}/runs", response_model=List[WorkflowExecutionResponse])
async def list_workflow_runs(
    workflow_id: str,
    limit: int = Query(50, ge=1, le=100),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves chronological execution logs and telemetry for a workflow.
    """
    user, org, role = tenant_context
    stmt = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.workflow_id == workflow_id,
            WorkflowExecution.organization_id == org.id
        )
        .order_by(desc(WorkflowExecution.started_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    runs = res.scalars().all()

    return [
        WorkflowExecutionResponse(
            id=r.id,
            workflow_id=r.workflow_id,
            trigger_event_type=r.trigger_event_type,
            status=r.status,
            execution_time_ms=r.execution_time_ms,
            started_at=r.started_at,
            completed_at=r.completed_at,
            step_count=len(r.step_logs or []),
            error_message=r.error_message
        )
        for r in runs
    ]

@router.get("/{workflow_id}/runs/{run_id}", response_model=WorkflowExecutionDetail)
async def get_workflow_run_detail(
    workflow_id: str,
    run_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves granular step logs and input/output payload for an execution run.
    """
    user, org, role = tenant_context
    stmt = (
        select(WorkflowExecution)
        .where(
            WorkflowExecution.id == run_id,
            WorkflowExecution.workflow_id == workflow_id,
            WorkflowExecution.organization_id == org.id
        )
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution record not found")
    return run
