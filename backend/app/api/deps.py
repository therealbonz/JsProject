import hashlib
from datetime import datetime, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.tenant import User, Organization, OrganizationMembership
from app.models.developer import ApiKey

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db)
) -> User:
    if x_api_key:
        hashed = hashlib.sha256(x_api_key.strip().encode()).hexdigest()
        stmt = select(ApiKey).where(ApiKey.hashed_key == hashed, ApiKey.is_active == True)
        api_key = (await db.execute(stmt)).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )
        if api_key.expires_at:
            exp = api_key.expires_at if api_key.expires_at.tzinfo else api_key.expires_at.replace(tzinfo=timezone.utc)
            if exp < now:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key has expired",
                    headers={"WWW-Authenticate": "ApiKey"},
                )
        api_key.last_used_at = now
        db.add(api_key)
        await db.commit()

        if api_key.created_by_user_id:
            user_stmt = select(User).where(User.id == api_key.created_by_user_id)
            user = (await db.execute(user_stmt)).scalar_one_or_none()
            if user:
                return user
        # Fallback to org admin user
        mem_stmt = select(OrganizationMembership).where(
            OrganizationMembership.organization_id == api_key.organization_id,
            OrganizationMembership.role == "admin"
        )
        mem = (await db.execute(mem_stmt)).scalars().first()
        if mem:
            u_stmt = select(User).where(User.id == mem.user_id)
            user = (await db.execute(u_stmt)).scalar_one_or_none()
            if user:
                return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key owner not found",
        )

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
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    db: AsyncSession = Depends(get_db)
) -> tuple[User, Organization, str]:
    """
    Enforces multi-tenant scoping.
    Determines active organization and validates user membership or API key authorization.
    Returns (user, organization, role).
    """
    if x_api_key:
        hashed = hashlib.sha256(x_api_key.strip().encode()).hexdigest()
        stmt = select(ApiKey).where(ApiKey.hashed_key == hashed, ApiKey.is_active == True)
        api_key = (await db.execute(stmt)).scalar_one_or_none()
        if api_key:
            org_stmt = select(Organization).where(Organization.id == api_key.organization_id, Organization.status == "active")
            org = (await db.execute(org_stmt)).scalar_one_or_none()
            if org:
                return current_user, org, "admin"

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

