import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization
from app.models.crm import ProspectCampaign, Lead
from app.services.prospect_import_service import ProspectImportService
from app.schemas.prospects import (
    ProspectImportPreview,
    ProspectImportResponse,
    ProspectCampaignResponse,
    ProspectCampaignLeadItem
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Prospect Uploads & Campaigns"])


@router.get("/crm/prospects/template")
async def download_prospect_template():
    """
    Downloads an RFC 4180 compliant sample CSV template with standard headers and example records.
    """
    csv_text = ProspectImportService.generate_sample_csv()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="apex_prospect_import_template.csv"'}
    )


@router.post("/crm/prospects/upload")
async def upload_prospect_csv(
    file: UploadFile = File(..., description="CSV or text file containing prospect list"),
    campaign_name: Optional[str] = Form(None, description="Name for the outreach campaign"),
    trade_service: str = Form("carpet_cleaning", description="Target trade: carpet_cleaning, lawn_care, roofing, general"),
    skip_duplicates: bool = Form(True, description="Skip numbers already in CRM or repeated in file"),
    dry_run: bool = Form(False, description="Preview parsed headers and sample rows without saving"),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Uploads a prospect CSV list into the CRM:
    - Fuzzy matches column headers
    - Sanitizes and validates phone numbers to E.164
    - Deduplicates against existing organization contacts
    - If dry_run=True, returns preview of mapped columns and first 5 rows
    - If dry_run=False, commits records to ProspectCampaign, Company, Contact, and Lead
    """
    user, org, _ = tenant_context

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    filename = file.filename or "uploaded_prospects.csv"

    if dry_run:
        preview = await ProspectImportService.preview_import(
            file_bytes=file_bytes,
            default_trade=trade_service,
            organization_id=org.id,
            db=db,
            sample_limit=5
        )
        return preview

    result = await ProspectImportService.execute_import(
        file_bytes=file_bytes,
        campaign_name=campaign_name or f"{trade_service.replace('_', ' ').title()} Outreach",
        trade_service=trade_service,
        organization=org,
        db=db,
        skip_duplicates=skip_duplicates,
        source_filename=filename
    )
    return result


@router.get("/crm/prospects/campaigns", response_model=List[ProspectCampaignResponse])
async def list_prospect_campaigns(
    trade: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists prospect campaigns for the tenant organization with ingestion counts and status.
    """
    user, org, _ = tenant_context
    stmt = (
        select(ProspectCampaign)
        .where(ProspectCampaign.organization_id == org.id)
        .order_by(desc(ProspectCampaign.created_at))
    )
    if trade:
        stmt = stmt.where(ProspectCampaign.trade_service == trade)
    if status_filter:
        stmt = stmt.where(ProspectCampaign.status == status_filter)

    res = await db.execute(stmt)
    campaigns = res.scalars().all()

    return [
        ProspectCampaignResponse(
            id=c.id,
            name=c.name,
            trade_service=c.trade_service,
            status=c.status,
            total_rows=c.total_rows,
            valid_count=c.valid_count,
            duplicate_count=c.duplicate_count,
            error_count=c.error_count,
            dialed_count=c.dialed_count,
            connected_count=c.connected_count,
            booked_count=c.booked_count,
            source_filename=c.source_filename,
            created_at=c.created_at.isoformat() if c.created_at else None
        )
        for c in campaigns
    ]


@router.get("/crm/prospects/campaigns/{campaign_id}")
async def get_campaign_details(
    campaign_id: str,
    limit: int = Query(50, ge=1, le=200),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns campaign details along with the leads attached to this campaign.
    """
    user, org, _ = tenant_context
    stmt = (
        select(ProspectCampaign)
        .where(
            ProspectCampaign.id == campaign_id,
            ProspectCampaign.organization_id == org.id
        )
    )
    res = await db.execute(stmt)
    campaign = res.scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    leads_stmt = (
        select(Lead)
        .options(
            selectinload(Lead.contact),
            selectinload(Lead.company)
        )
        .where(
            Lead.campaign_id == campaign_id,
            Lead.organization_id == org.id
        )
        .order_by(desc(Lead.created_at))
        .limit(limit)
    )
    leads_res = await db.execute(leads_stmt)
    leads = leads_res.scalars().all()

    return {
        "campaign": ProspectCampaignResponse(
            id=campaign.id,
            name=campaign.name,
            trade_service=campaign.trade_service,
            status=campaign.status,
            total_rows=campaign.total_rows,
            valid_count=campaign.valid_count,
            duplicate_count=campaign.duplicate_count,
            error_count=campaign.error_count,
            dialed_count=campaign.dialed_count,
            connected_count=campaign.connected_count,
            booked_count=campaign.booked_count,
            source_filename=campaign.source_filename,
            created_at=campaign.created_at.isoformat() if campaign.created_at else None
        ),
        "leads_count": len(leads),
        "leads": [
            ProspectCampaignLeadItem(
                id=l.id,
                homeowner_name=f"{l.contact.first_name} {l.contact.last_name}".strip() if l.contact else "Prospect",
                phone=l.contact.phone if l.contact else None,
                email=l.contact.email if l.contact else None,
                address=l.company.address if l.company else None,
                pipeline_stage=l.pipeline_stage,
                lead_score=l.lead_score,
                created_at=l.created_at.isoformat() if l.created_at else None
            )
            for l in leads
        ]
    }


# =========================================================================
# PUBLIC / RESIDENTIAL PORTAL CONVENIENCE ENDPOINT
# =========================================================================

@router.post("/residential/prospects/upload")
async def upload_residential_prospect_csv(
    file: UploadFile = File(...),
    campaign_name: Optional[str] = Form(None),
    trade_service: str = Form("carpet_cleaning"),
    skip_duplicates: bool = Form(True),
    dry_run: bool = Form(False),
    db: AsyncSession = Depends(get_db)
):
    """
    Public convenience endpoint for the Residential Sales Bot portal:
    Resolves default active organization and performs prospect list upload or dry-run preview.
    """
    # Pick default active organization
    org_res = await db.execute(select(Organization).where(Organization.status == "active").limit(1))
    org = org_res.scalar_one_or_none()
    if not org:
        # Fallback to any organization
        org_res = await db.execute(select(Organization).limit(1))
        org = org_res.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No organization configured")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")

    filename = file.filename or "uploaded_prospects.csv"

    if dry_run:
        preview = await ProspectImportService.preview_import(
            file_bytes=file_bytes,
            default_trade=trade_service,
            organization_id=org.id,
            db=db,
            sample_limit=5
        )
        return preview

    result = await ProspectImportService.execute_import(
        file_bytes=file_bytes,
        campaign_name=campaign_name or f"{trade_service.replace('_', ' ').title()} Prospects",
        trade_service=trade_service,
        organization=org,
        db=db,
        skip_duplicates=skip_duplicates,
        source_filename=filename
    )
    return result
