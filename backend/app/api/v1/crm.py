from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization
from app.models.crm import Company, Contact, Lead, Product, KnowledgeDocument
from app.models.conversation import Conversation
from app.schemas.crm import (
    LeadCreate, LeadResponse, LeadUpdate,
    ProductCreate, ProductResponse,
    CompanyCreate, CompanyResponse,
    KnowledgeDocCreate, KnowledgeDocResponse
)

router = APIRouter(prefix="/crm", tags=["CRM & Pipeline"])

@router.get("/leads", response_model=List[LeadResponse])
async def list_leads(
    stage: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(Lead).options(
        selectinload(Lead.company),
        selectinload(Lead.contact)
    ).where(Lead.organization_id == org.id)

    if stage:
        stmt = stmt.where(Lead.pipeline_stage == stage)
    if status_filter:
        stmt = stmt.where(Lead.status == status_filter)
    
    stmt = stmt.order_by(Lead.created_at.desc())
    result = await db.execute(stmt)
    leads = result.scalars().all()
    return leads

@router.post("/leads", response_model=LeadResponse)
async def create_lead(
    payload: LeadCreate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context

    # 1. Find or create company
    comp_stmt = select(Company).where(
        Company.organization_id == org.id,
        Company.name == payload.company_name
    )
    comp_res = await db.execute(comp_stmt)
    company = comp_res.scalar_one_or_none()

    if not company:
        company = Company(
            organization_id=org.id,
            name=payload.company_name,
            domain=payload.company_domain,
            industry=payload.industry or "Commercial Services"
        )
        db.add(company)
        await db.flush()

    # 2. Find or create contact
    contact_stmt = select(Contact).where(
        Contact.organization_id == org.id,
        Contact.email == payload.contact_email
    )
    contact_res = await db.execute(contact_stmt)
    contact = contact_res.scalar_one_or_none()

    if not contact:
        contact = Contact(
            organization_id=org.id,
            company_id=company.id,
            first_name=payload.contact_first_name,
            last_name=payload.contact_last_name,
            email=payload.contact_email,
            job_title=payload.contact_title or "Purchasing Manager",
            decision_maker_role=payload.decision_maker_role or "purchasing",
            is_primary=True
        )
        db.add(contact)
        await db.flush()

    # 3. Create Lead
    lead = Lead(
        organization_id=org.id,
        company_id=company.id,
        contact_id=contact.id,
        lead_score=50,
        pipeline_stage="new",
        status="active"
    )
    db.add(lead)
    await db.flush()

    # 4. Create primary conversation container for email
    conversation = Conversation(
        organization_id=org.id,
        lead_id=lead.id,
        channel="email",
        status="active"
    )
    db.add(conversation)

    await db.commit()

    # Reload with relationships
    stmt = select(Lead).options(
        selectinload(Lead.company),
        selectinload(Lead.contact)
    ).where(Lead.id == lead.id)
    res = await db.execute(stmt)
    return res.scalar_one()

@router.get("/leads/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(Lead).options(
        selectinload(Lead.company),
        selectinload(Lead.contact)
    ).where(Lead.id == lead_id, Lead.organization_id == org.id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
    return lead

@router.patch("/leads/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    payload: LeadUpdate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(Lead).options(
        selectinload(Lead.company),
        selectinload(Lead.contact)
    ).where(Lead.id == lead_id, Lead.organization_id == org.id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    if payload.pipeline_stage is not None:
        lead.pipeline_stage = payload.pipeline_stage
    if payload.lead_score is not None:
        lead.lead_score = payload.lead_score
    if payload.status is not None:
        lead.status = payload.status
    if payload.research_summary is not None:
        lead.research_summary = payload.research_summary

    await db.commit()
    await db.refresh(lead)
    return lead

@router.get("/products", response_model=List[ProductResponse])
async def list_products(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(Product).where(Product.organization_id == org.id, Product.is_active == True)
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/products", response_model=ProductResponse)
async def create_product(
    payload: ProductCreate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    product = Product(
        organization_id=org.id,
        name=payload.name,
        sku=payload.sku,
        category=payload.category,
        description=payload.description,
        unit_price=payload.unit_price,
        min_allowed_price=payload.min_allowed_price,
        currency=payload.currency
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product

@router.get("/pipeline/stats")
async def get_pipeline_stats(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(Lead.pipeline_stage, func.count(Lead.id)).where(
        Lead.organization_id == org.id
    ).group_by(Lead.pipeline_stage)
    result = await db.execute(stmt)
    stats = {stage: count for stage, count in result.all()}

    stages = ["new", "researching", "ready_contact", "contacted", "connected", "qualified", "proposal", "negotiation", "won", "lost"]
    ordered_stats = {s: stats.get(s, 0) for s in stages}
    return ordered_stats
