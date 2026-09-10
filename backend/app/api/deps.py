from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.tenant import User, Organization, OrganizationMembership

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    
    stmt = select(User).where(User.id == user_id, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    
    return user

async def get_current_tenant(
    current_user: User = Depends(get_current_user),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    db: AsyncSession = Depends(get_db)
) -> tuple[User, Organization, str]:
    """
    Enforces multi-tenant scoping.
    Determines active organization and validates user membership.
    Returns (user, organization, role).
    """
    # Look for membership
    if x_organization_id:
        stmt = select(OrganizationMembership, Organization).join(
            Organization, Organization.id == OrganizationMembership.organization_id
        ).where(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.organization_id == x_organization_id,
            Organization.status == "active"
        )
    else:
        # Pick user's primary/first organization
        stmt = select(OrganizationMembership, Organization).join(
            Organization, Organization.id == OrganizationMembership.organization_id
        ).where(
            OrganizationMembership.user_id == current_user.id,
            Organization.status == "active"
        )
    
    result = await db.execute(stmt)
    row = result.first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not an active member of this organization",
        )
    
    membership, organization = row
    return current_user, organization, membership.role

def require_roles(allowed_roles: list[str]):
    """
    Dependency factory enforcing Role-Based Access Control (RBAC).
    Validates that the caller's tenant role is in allowed_roles.
    'super_admin' and 'admin' always possess unrestricted access.
    """
    async def role_checker(
        tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant)
    ) -> tuple[User, Organization, str]:
        user, org, role = tenant_context
        if role in ["super_admin", "admin"]:
            return tenant_context
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Operation requires one of the following roles: {allowed_roles}. Your current role is '{role}'."
            )
        return tenant_context

    return role_checker

