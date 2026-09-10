from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, ConfigDict

class TeamMemberInviteRequest(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "sales_rep"  # admin, sales_manager, sales_rep, fulfillment_specialist, billing_officer, viewer
    password: Optional[str] = None  # If omitted, a secure default temporary password is generated

class TeamMemberRoleUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

class TeamMemberResponse(BaseModel):
    id: str  # Membership ID
    user_id: str
    organization_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class RolePermissionInfo(BaseModel):
    role: str
    title: str
    badge_color: str
    description: str
    permissions: List[str]

class AuditLogDetailedResponse(BaseModel):
    id: str
    organization_id: str
    actor_type: str
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    actor_role: Optional[str] = None
    action: str
    target_entity: Optional[str] = None
    target_id: Optional[str] = None
    status: str = "success"
    ip_address: Optional[str] = None
    payload: Dict[str, Any] = {}
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class AuditTrailOverviewResponse(BaseModel):
    total_events: int
    today_events: int
    actions_breakdown: Dict[str, int]
    actors_breakdown: Dict[str, int]
    recent_logs: List[AuditLogDetailedResponse]
