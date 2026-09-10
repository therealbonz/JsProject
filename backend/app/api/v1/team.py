import uuid
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import hash_password
from app.api.deps import get_current_tenant, require_roles
from app.models.tenant import User, Organization, OrganizationMembership
from app.models.hitl import AuditLog
from app.schemas.team_rbac import (
    TeamMemberInviteRequest, TeamMemberRoleUpdateRequest, TeamMemberResponse,
    RolePermissionInfo, AuditLogDetailedResponse, AuditTrailOverviewResponse
)
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/team", tags=["Team RBAC & Audit Trails"])

ROLE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "role": "admin",
        "title": "Tenant Administrator",
        "badge_color": "indigo",
        "description": "Full access to platform settings, team management, billing, white-label branding, and HITL overrides.",
        "permissions": ["all:manage", "team:manage", "settings:write", "billing:manage", "hitl:approve", "fulfillment:manage"]
    },
    {
        "role": "sales_manager",
        "title": "Sales Operations Manager",
        "badge_color": "emerald",
        "description": "Manages client accounts, deal pipelines, proposals, and reviews Human-in-the-Loop discount requests.",
        "permissions": ["crm:write", "pipeline:manage", "hitl:approve", "quotes:manage", "reports:view"]
    },
    {
        "role": "sales_rep",
        "title": "Sales Representative",
        "badge_color": "purple",
        "description": "Conducts account outreach, researches leads, sends catalog-grounded emails, and logs client touchpoints.",
        "permissions": ["leads:manage", "conversations:write", "ai_agent:trigger", "calls:log"]
    },
    {
        "role": "fulfillment_specialist",
        "title": "Supply Chain & Fulfillment Specialist",
        "badge_color": "amber",
        "description": "Operates supplier catalog adapters, triggers autofill procurement, manages EDI 850/856, and parcel dispatch.",
        "permissions": ["procurement:manage", "suppliers:manage", "edi:dispatch", "tracking:update"]
    },
    {
        "role": "billing_officer",
        "title": "Finance & Billing Officer",
        "badge_color": "sky",
        "description": "Inspects recurring billing settlements, manages stored cards-on-file, and generates printable PDF invoices.",
        "permissions": ["billing:write", "invoices:generate", "charges:execute", "financials:view"]
    },
    {
        "role": "viewer",
        "title": "Read-Only Auditor / Viewer",
        "badge_color": "slate",
        "description": "Read-only access across CRM rosters, pipeline reports, license telemetry, and tracking portals.",
        "permissions": ["crm:read", "reports:view", "tracking:view"]
    }
]

@router.get("/roles", response_model=List[RolePermissionInfo])
async def list_roles(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant)
):
    """Retrieve predefined role dictionary and security permission scopes."""
    return ROLE_DEFINITIONS

@router.get("/members", response_model=List[TeamMemberResponse])
async def list_team_members(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """List all team members enrolled in the active tenant organization."""
    _, org, _ = tenant_context
    stmt = select(OrganizationMembership).options(
        selectinload(OrganizationMembership.user)
    ).where(
        OrganizationMembership.organization_id == org.id
    ).order_by(OrganizationMembership.created_at.asc())

    res = await db.execute(stmt)
    memberships = res.scalars().all()

    output = []
    for m in memberships:
        output.append(
            TeamMemberResponse(
                id=m.id,
                user_id=m.user_id,
                organization_id=m.organization_id,
                email=m.user.email,
                full_name=m.user.full_name,
                role=m.role,
                is_active=m.user.is_active,
                created_at=m.created_at
            )
        )
    return output

@router.post("/invite", response_model=TeamMemberResponse)
async def invite_team_member(
    payload: TeamMemberInviteRequest,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Invite or enroll a new team member with a specified role into the organization.
    Restricted to Tenant Administrators.
    """
    current_user, org, caller_role = tenant_context

    valid_roles = [r["role"] for r in ROLE_DEFINITIONS] + ["super_admin"]
    if payload.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Must be one of: {valid_roles}"
        )

    # Check if user exists
    user_stmt = select(User).where(User.email == payload.email)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if not user:
        # Create user account
        temp_pwd = payload.password or f"TempSecret!{uuid.uuid4().hex[:6]}"
        user = User(
            email=payload.email,
            hashed_password=hash_password(temp_pwd),
            full_name=payload.full_name,
            is_active=True,
            is_superuser=False
        )
        db.add(user)
        await db.flush()

    # Check if already a member of this org
    mem_stmt = select(OrganizationMembership).where(
        OrganizationMembership.organization_id == org.id,
        OrganizationMembership.user_id == user.id
    )
    mem_res = await db.execute(mem_stmt)
    membership = mem_res.scalar_one_or_none()

    if membership:
        membership.role = payload.role
    else:
        membership = OrganizationMembership(
            organization_id=org.id,
            user_id=user.id,
            role=payload.role
        )
        db.add(membership)

    await db.flush()

    # Log audit trail
    await audit_service.log_event(
        db=db,
        org_id=org.id,
        action="team.member_invited",
        actor_type="user",
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=caller_role,
        target_entity="organization_membership",
        target_id=membership.id,
        status="success",
        payload={
            "invited_email": payload.email,
            "invited_name": payload.full_name,
            "assigned_role": payload.role
        }
    )

    await db.commit()
    await db.refresh(membership)

    return TeamMemberResponse(
        id=membership.id,
        user_id=user.id,
        organization_id=org.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        is_active=user.is_active,
        created_at=membership.created_at
    )

@router.patch("/members/{membership_id}", response_model=TeamMemberResponse)
async def update_member_role(
    membership_id: str,
    payload: TeamMemberRoleUpdateRequest,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Update role or active status of a team member. Enforces last-admin safety protection."""
    current_user, org, caller_role = tenant_context

    stmt = select(OrganizationMembership).options(
        selectinload(OrganizationMembership.user)
    ).where(
        OrganizationMembership.id == membership_id,
        OrganizationMembership.organization_id == org.id
    )
    res = await db.execute(stmt)
    membership = res.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Team membership not found.")

    # Prevent demoting the last active admin
    if payload.role and payload.role != "admin" and membership.role in ["admin", "super_admin"]:
        count_admins_stmt = select(func.count(OrganizationMembership.id)).where(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.role.in_(["admin", "super_admin"])
        )
        admin_count = (await db.execute(count_admins_stmt)).scalar() or 0
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the sole remaining Administrator of this organization."
            )

    old_role = membership.role
    if payload.role:
        valid_roles = [r["role"] for r in ROLE_DEFINITIONS] + ["super_admin"]
        if payload.role not in valid_roles:
            raise HTTPException(status_code=400, detail=f"Invalid role: {payload.role}")
        membership.role = payload.role

    if payload.is_active is not None and membership.user:
        membership.user.is_active = payload.is_active

    await audit_service.log_event(
        db=db,
        org_id=org.id,
        action="team.role_updated",
        actor_type="user",
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=caller_role,
        target_entity="organization_membership",
        target_id=membership.id,
        status="success",
        payload={
            "target_user_id": membership.user_id,
            "target_user_email": membership.user.email,
            "previous_role": old_role,
            "new_role": membership.role,
            "is_active": membership.user.is_active
        }
    )

    await db.commit()
    await db.refresh(membership)

    return TeamMemberResponse(
        id=membership.id,
        user_id=membership.user.id,
        organization_id=org.id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
        is_active=membership.user.is_active,
        created_at=membership.created_at
    )

@router.delete("/members/{membership_id}")
async def remove_team_member(
    membership_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin"])),
    db: AsyncSession = Depends(get_db)
):
    """Remove a team member from the organization."""
    current_user, org, caller_role = tenant_context

    stmt = select(OrganizationMembership).options(
        selectinload(OrganizationMembership.user)
    ).where(
        OrganizationMembership.id == membership_id,
        OrganizationMembership.organization_id == org.id
    )
    res = await db.execute(stmt)
    membership = res.scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=404, detail="Team membership not found.")

    if membership.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself as administrator.")

    if membership.role in ["admin", "super_admin"]:
        count_admins_stmt = select(func.count(OrganizationMembership.id)).where(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.role.in_(["admin", "super_admin"])
        )
        admin_count = (await db.execute(count_admins_stmt)).scalar() or 0
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the sole Administrator.")

    target_email = membership.user.email if membership.user else "unknown"
    await db.delete(membership)

    await audit_service.log_event(
        db=db,
        org_id=org.id,
        action="team.member_removed",
        actor_type="user",
        actor_id=current_user.id,
        actor_email=current_user.email,
        actor_role=caller_role,
        target_entity="organization_membership",
        target_id=membership_id,
        status="success",
        payload={"removed_user_email": target_email}
    )

    await db.commit()
    return {"success": True, "message": f"Team member {target_email} has been removed from {org.name}."}

@router.get("/audit-logs", response_model=List[AuditLogDetailedResponse])
async def list_audit_logs(
    action: Optional[str] = Query(None, description="Prefix filter, e.g. 'team', 'edi', 'auth'"),
    actor_type: Optional[str] = Query(None),
    actor_email: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve filterable audit logs for the current organization."""
    _, org, _ = tenant_context
    logs = await audit_service.query_logs(
        db=db,
        org_id=org.id,
        action_prefix=action,
        actor_type=actor_type,
        actor_email=actor_email,
        status=status_filter,
        limit=limit,
        offset=offset
    )
    return logs

@router.get("/audit-logs/overview", response_model=AuditTrailOverviewResponse)
async def get_audit_overview(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """Summary metrics of audit trail activity and action distribution."""
    _, org, _ = tenant_context
    overview = await audit_service.get_overview_metrics(db, org.id)
    return overview

@router.get("/audit-logs/export")
async def export_audit_logs(
    format: str = Query("csv", pattern="^(csv|json)$"),
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "sales_manager"])),
    db: AsyncSession = Depends(get_db)
):
    """Export compliance audit logs in standard RFC 4180 CSV or JSON format."""
    _, org, _ = tenant_context
    logs = await audit_service.query_logs(db=db, org_id=org.id, limit=1000)

    if format == "csv":
        csv_content = audit_service.export_to_csv(logs)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=audit_trail_{org.slug}.csv"}
        )
    else:
        return [AuditLogDetailedResponse.model_validate(l).model_dump() for l in logs]
