import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.tenant import User, Organization
from app.api.deps import get_current_tenant, require_roles
from app.services.custom_domain_service import CustomDomainService
from app.schemas.custom_domain import (
    CustomDomainCreate,
    CustomDomainUpdate,
    CustomDomainResponse,
    DomainVerificationResult,
    PublicDomainResolutionResponse,
    NginxConfigResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/domains", tags=["Custom White-Label Domains & Host Routing"])

@router.get("/public/resolve", response_model=PublicDomainResolutionResponse)
async def resolve_public_host_branding(
    request: Request,
    host: Optional[str] = Query(None, description="Optional explicit host to resolve, defaults to incoming request host"),
    db: AsyncSession = Depends(get_db)
):
    """
    Public resolution endpoint for incoming hostnames.
    Matches custom domain to tenant branding, custom themes, and portal settings.
    Requires no authentication.
    """
    effective_host = host or request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    return await CustomDomainService.resolve_host_branding(db, effective_host)

@router.post("", response_model=CustomDomainResponse, status_code=status.HTTP_201_CREATED)
async def register_custom_domain(
    payload: CustomDomainCreate,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Registers a new custom domain or subdomain for the current tenant organization.
    Generates unique CNAME and TXT challenge tokens.
    """
    user, org, role = tenant_context
    try:
        domain_rec = await CustomDomainService.register_domain(db, org.id, payload)
        return CustomDomainService.to_response_dto(domain_rec)
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ex))
    except Exception as ex:
        logger.error(f"Error registering custom domain: {ex}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to register custom domain.")

@router.get("", response_model=List[CustomDomainResponse])
async def list_custom_domains(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists all custom domains configured for the authenticated organization.
    """
    user, org, role = tenant_context
    domains = await CustomDomainService.list_domains(db, org.id)
    return [CustomDomainService.to_response_dto(d) for d in domains]

@router.get("/{domain_id}", response_model=CustomDomainResponse)
async def get_custom_domain(
    domain_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves full details and DNS setup instructions for a specific custom domain.
    """
    user, org, role = tenant_context
    domain_rec = await CustomDomainService.get_domain(db, domain_id, org.id)
    if not domain_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom domain not found")
    return CustomDomainService.to_response_dto(domain_rec)

@router.post("/{domain_id}/verify", response_model=DomainVerificationResult)
async def verify_custom_domain_dns(
    domain_id: str,
    simulate: bool = Query(False, description="Simulate DNS match for sandbox or unit testing"),
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Performs live DNS resolution checks against CNAME target or TXT challenge token.
    On success, transitions verification status to 'verified' and provisions SSL status to 'active'.
    """
    user, org, role = tenant_context
    try:
        return await CustomDomainService.verify_domain_dns(db, domain_id, org.id, force_simulate=simulate)
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))
    except Exception as ex:
        logger.error(f"Error during domain DNS verification: {ex}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="DNS verification execution failed.")

@router.post("/{domain_id}/primary", response_model=CustomDomainResponse)
async def set_primary_custom_domain(
    domain_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Sets the specified domain as the primary branded domain for the organization.
    """
    user, org, role = tenant_context
    try:
        updated = await CustomDomainService.set_primary_domain(db, domain_id, org.id)
        return CustomDomainService.to_response_dto(updated)
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))

@router.put("/{domain_id}", response_model=CustomDomainResponse)
async def update_custom_domain(
    domain_id: str,
    payload: CustomDomainUpdate,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Updates active status, primary flag, or theme overrides for a custom domain.
    """
    user, org, role = tenant_context
    try:
        updated = await CustomDomainService.update_domain(db, domain_id, org.id, payload)
        return CustomDomainService.to_response_dto(updated)
    except ValueError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ex))

@router.get("/{domain_id}/nginx-config", response_model=NginxConfigResponse)
async def get_domain_nginx_config(
    domain_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Generates a production-ready Nginx reverse-proxy configuration block and Certbot SSL command.
    """
    user, org, role = tenant_context
    domain_rec = await CustomDomainService.get_domain(db, domain_id, org.id)
    if not domain_rec:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom domain not found")
    return CustomDomainService.generate_nginx_config(domain_rec)

@router.delete("/{domain_id}")
async def delete_custom_domain(
    domain_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(require_roles(["admin", "super_admin"])),
    db: AsyncSession = Depends(get_db)
):
    """
    Removes a custom domain from the organization.
    """
    user, org, role = tenant_context
    deleted = await CustomDomainService.delete_domain(db, domain_id, org.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Custom domain not found")
    return {"status": "success", "message": "Custom domain removed successfully"}
