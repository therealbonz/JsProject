import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models.custom_domain import CustomDomain
from app.services.custom_domain_service import CustomDomainService, RESERVED_DOMAINS

logger = logging.getLogger(__name__)

class TenantHostMiddleware(BaseHTTPMiddleware):
    """
    Middleware that intercepts incoming HTTP requests, extracts Host or X-Forwarded-Host,
    and dynamically resolves the tenant organization if the host corresponds to an active,
    verified custom white-label domain.
    """
    async def dispatch(self, request: Request, call_next):
        host_header = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        normalized = CustomDomainService.normalize_domain(host_header)

        request.state.custom_domain = None
        request.state.tenant_org = None
        request.state.tenant_id = None

        if normalized and normalized not in RESERVED_DOMAINS:
            try:
                async with AsyncSessionLocal() as session:
                    stmt = (
                        select(CustomDomain)
                        .options(selectinload(CustomDomain.organization))
                        .where(
                            CustomDomain.domain == normalized,
                            CustomDomain.is_active == True,
                            CustomDomain.verification_status == "verified"
                        )
                    )
                    res = await session.execute(stmt)
                    custom_domain = res.scalar_one_or_none()
                    if custom_domain and custom_domain.organization:
                        request.state.custom_domain = custom_domain
                        request.state.tenant_org = custom_domain.organization
                        request.state.tenant_id = custom_domain.organization.id
            except Exception as e:
                logger.debug("TenantHostMiddleware domain lookup skipped or failed: %s", e)

        return await call_next(request)
