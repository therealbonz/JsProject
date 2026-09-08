from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization
from app.models.crm import Company, Contact, Lead, Product, KnowledgeDocument, CallLog, ClientAccount, ClientSale
from app.models.conversation import Conversation
from app.models.hitl import AuditLog
from app.schemas.crm import (
    LeadCreate, LeadResponse, LeadUpdate,
    CallLogCreate, CallLogResponse,
    ProductCreate, ProductResponse,
    CompanyCreate, CompanyResponse,
    KnowledgeDocCreate, KnowledgeDocResponse,
    ClientAccountCreate, ClientAccountUpdate, ClientAccountResponse,
    ClientSaleCreate, ClientSaleResponse, ClientSalesOverviewStats,
    LeadConversionPayload
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
        selectinload(Lead.contact),
        selectinload(Lead.call_logs)
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
    user, org, _ = tenant_context

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
            industry=payload.industry or "Commercial Services",
            notes=payload.notes
        )
        db.add(company)
        await db.flush()
    elif payload.notes and not company.notes:
        company.notes = payload.notes

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
    initial_stage = "new"
    call_time = payload.last_call_at
    if payload.last_call_notes or payload.last_call_at:
        call_time = payload.last_call_at or datetime.now(timezone.utc)
        outcome = payload.last_call_outcome or "connected"
        initial_stage = "connected" if outcome in ["connected", "scheduled_demo"] else "contacted"

    lead = Lead(
        organization_id=org.id,
        company_id=company.id,
        contact_id=contact.id,
        lead_score=50,
        pipeline_stage=initial_stage,
        status="active",
        notes=payload.notes,
        last_contacted_at=call_time,
        last_call_at=call_time,
        last_call_notes=payload.last_call_notes,
        last_call_outcome=payload.last_call_outcome if (payload.last_call_notes or payload.last_call_at) else None
    )
    db.add(lead)
    await db.flush()

    # 4. Create CallLog entry if call details were entered in Quick Add
    if payload.last_call_notes or payload.last_call_at:
        call_log = CallLog(
            organization_id=org.id,
            lead_id=lead.id,
            company_id=company.id,
            contact_id=contact.id,
            caller_name=user.full_name or "Sales Rep",
            called_at=call_time,
            duration_minutes=payload.call_duration_minutes or 0,
            outcome=payload.last_call_outcome or "connected",
            notes=payload.last_call_notes or "Initial call logged via Quick Add",
            next_steps="Follow up as needed"
        )
        db.add(call_log)

        audit = AuditLog(
            organization_id=org.id,
            actor_type="human_rep",
            actor_id=user.id,
            action="lead_call_logged",
            target_entity="lead",
            target_id=lead.id,
            payload={
                "outcome": call_log.outcome,
                "called_at": call_time.isoformat(),
                "notes_snippet": (call_log.notes[:60] + "...") if len(call_log.notes) > 60 else call_log.notes
            }
        )
        db.add(audit)

    # 5. Create primary conversation container for email
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
        selectinload(Lead.contact),
        selectinload(Lead.call_logs)
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
        selectinload(Lead.contact),
        selectinload(Lead.call_logs)
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
        selectinload(Lead.contact),
        selectinload(Lead.call_logs)
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
    if payload.notes is not None:
        lead.notes = payload.notes
    if payload.last_call_at is not None:
        lead.last_call_at = payload.last_call_at
        lead.last_contacted_at = payload.last_call_at
    if payload.last_call_notes is not None:
        lead.last_call_notes = payload.last_call_notes
    if payload.last_call_outcome is not None:
        lead.last_call_outcome = payload.last_call_outcome

    await db.commit()
    await db.refresh(lead)
    return lead

@router.post("/leads/{lead_id}/calls", response_model=CallLogResponse)
async def log_call_for_lead(
    lead_id: str,
    payload: CallLogCreate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    user, org, _ = tenant_context
    stmt = select(Lead).options(
        selectinload(Lead.company),
        selectinload(Lead.contact)
    ).where(Lead.id == lead_id, Lead.organization_id == org.id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    call_time = payload.called_at or datetime.now(timezone.utc)
    outcome = payload.outcome or "connected"

    call_log = CallLog(
        organization_id=org.id,
        lead_id=lead.id,
        company_id=lead.company_id,
        contact_id=lead.contact_id,
        caller_name=payload.caller_name or user.full_name or "Sales Rep",
        called_at=call_time,
        duration_minutes=payload.duration_minutes or 0,
        outcome=outcome,
        notes=payload.notes,
        next_steps=payload.next_steps
    )
    db.add(call_log)

    # Update Lead last call info
    lead.last_call_at = call_time
    lead.last_call_notes = payload.notes
    lead.last_call_outcome = outcome
    lead.last_contacted_at = call_time

    # Advance pipeline stage if early
    if lead.pipeline_stage in ["new", "ready_contact"]:
        lead.pipeline_stage = "connected" if outcome in ["connected", "scheduled_demo"] else "contacted"

    # Audit Trail
    audit = AuditLog(
        organization_id=org.id,
        actor_type="human_rep",
        actor_id=user.id,
        action="lead_call_logged",
        target_entity="lead",
        target_id=lead.id,
        payload={
            "outcome": outcome,
            "duration": payload.duration_minutes,
            "called_at": call_time.isoformat(),
            "notes_snippet": (payload.notes[:60] + "...") if len(payload.notes) > 60 else payload.notes
        }
    )
    db.add(audit)

    await db.commit()
    await db.refresh(call_log)
    return call_log

@router.get("/leads/{lead_id}/calls", response_model=List[CallLogResponse])
async def list_calls_for_lead(
    lead_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(Lead).where(Lead.id == lead_id, Lead.organization_id == org.id)
    lead_res = await db.execute(stmt)
    if not lead_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    call_stmt = select(CallLog).where(
        CallLog.lead_id == lead_id,
        CallLog.organization_id == org.id
    ).order_by(CallLog.called_at.desc())
    result = await db.execute(call_stmt)
    return result.scalars().all()

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

# ==============================================================================
# Client Sales CRM (CRM 2 - Active Clients, Order Tracking & Revenue Engine)
# ==============================================================================

@router.get("/clients/stats/overview", response_model=ClientSalesOverviewStats)
async def get_client_sales_overview(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context

    # Total revenue & active clients
    clients_stmt = select(ClientAccount).where(ClientAccount.organization_id == org.id)
    clients_res = await db.execute(clients_stmt)
    clients = clients_res.scalars().all()

    total_rev = sum(c.total_revenue for c in clients)
    active_count = sum(1 for c in clients if c.status == "active")

    # Completed orders
    sales_stmt = select(ClientSale).where(
        ClientSale.organization_id == org.id,
        ClientSale.status != "cancelled"
    )
    sales_res = await db.execute(sales_stmt)
    sales = sales_res.scalars().all()
    total_orders = len(sales)
    aov = (total_rev / total_orders) if total_orders > 0 else 0.0

    return ClientSalesOverviewStats(
        total_revenue=round(total_rev, 2),
        active_clients_count=active_count,
        total_orders_count=total_orders,
        average_order_value=round(aov, 2)
    )

@router.get("/clients", response_model=List[ClientAccountResponse])
async def list_clients(
    tier: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(ClientAccount).options(
        selectinload(ClientAccount.company),
        selectinload(ClientAccount.primary_contact),
        selectinload(ClientAccount.sales)
    ).where(ClientAccount.organization_id == org.id)

    if tier:
        stmt = stmt.where(ClientAccount.account_tier == tier)
    if status_filter:
        stmt = stmt.where(ClientAccount.status == status_filter)

    stmt = stmt.order_by(ClientAccount.total_revenue.desc(), ClientAccount.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/clients", response_model=ClientAccountResponse)
async def create_client(
    payload: ClientAccountCreate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    user, org, _ = tenant_context

    # 1. Company
    comp_stmt = select(Company).where(
        Company.organization_id == org.id,
        Company.name == payload.account_name
    )
    comp_res = await db.execute(comp_stmt)
    company = comp_res.scalar_one_or_none()

    if not company:
        company = Company(
            organization_id=org.id,
            name=payload.account_name,
            domain=payload.company_domain,
            industry=payload.industry or "Commercial Enterprise",
            notes=payload.notes
        )
        db.add(company)
        await db.flush()

    # 2. Contact
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
            phone=payload.contact_phone,
            job_title="Key Account Lead",
            decision_maker_role="purchasing",
            is_primary=True
        )
        db.add(contact)
        await db.flush()

    # 3. Client Account
    cadence = payload.reorder_cadence_days or 30
    now = datetime.now(timezone.utc)
    renewal = payload.renewal_date or (now + timedelta(days=365))
    next_reorder = now + timedelta(days=cadence)

    client = ClientAccount(
        organization_id=org.id,
        company_id=company.id,
        primary_contact_id=contact.id,
        account_name=payload.account_name,
        account_tier=payload.account_tier or "standard",
        status=payload.status or "active",
        total_revenue=0.0,
        order_count=0,
        contract_start_date=now,
        renewal_date=renewal,
        reorder_cadence_days=cadence,
        next_reorder_date=next_reorder,
        account_manager=user.full_name or "Sales Director",
        notes=payload.notes
    )
    db.add(client)

    audit = AuditLog(
        organization_id=org.id,
        actor_type="human_rep",
        actor_id=user.id,
        action="client_account_created",
        target_entity="client_account",
        target_id=client.id,
        payload={"client_name": client.account_name, "tier": client.account_tier}
    )
    db.add(audit)

    await db.commit()

    # Reload with relationships
    stmt = select(ClientAccount).options(
        selectinload(ClientAccount.company),
        selectinload(ClientAccount.primary_contact),
        selectinload(ClientAccount.sales)
    ).where(ClientAccount.id == client.id)
    res = await db.execute(stmt)
    return res.scalar_one()

@router.get("/clients/{client_id}", response_model=ClientAccountResponse)
async def get_client(
    client_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(ClientAccount).options(
        selectinload(ClientAccount.company),
        selectinload(ClientAccount.primary_contact),
        selectinload(ClientAccount.sales)
    ).where(ClientAccount.id == client_id, ClientAccount.organization_id == org.id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")
    return client

@router.patch("/clients/{client_id}", response_model=ClientAccountResponse)
async def update_client(
    client_id: str,
    payload: ClientAccountUpdate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(ClientAccount).options(
        selectinload(ClientAccount.company),
        selectinload(ClientAccount.primary_contact),
        selectinload(ClientAccount.sales)
    ).where(ClientAccount.id == client_id, ClientAccount.organization_id == org.id)
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")

    if payload.account_name is not None:
        client.account_name = payload.account_name
    if payload.account_tier is not None:
        client.account_tier = payload.account_tier
    if payload.status is not None:
        client.status = payload.status
    if payload.reorder_cadence_days is not None:
        client.reorder_cadence_days = payload.reorder_cadence_days
    if payload.renewal_date is not None:
        client.renewal_date = payload.renewal_date
    if payload.account_manager is not None:
        client.account_manager = payload.account_manager
    if payload.notes is not None:
        client.notes = payload.notes

    await db.commit()
    await db.refresh(client)
    return client

@router.post("/clients/{client_id}/sales", response_model=ClientSaleResponse)
async def log_client_sale(
    client_id: str,
    payload: ClientSaleCreate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    user, org, _ = tenant_context

    stmt = select(ClientAccount).where(
        ClientAccount.id == client_id,
        ClientAccount.organization_id == org.id
    )
    result = await db.execute(stmt)
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")

    now = datetime.now(timezone.utc)
    sale_time = payload.sale_date or now
    order_num = payload.order_number or f"SO-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"

    sale = ClientSale(
        organization_id=org.id,
        client_id=client.id,
        order_number=order_num,
        amount=payload.amount,
        sale_date=sale_time,
        status=payload.status or "completed",
        payment_method=payload.payment_method or "credit_terms_30",
        items_summary=payload.items_summary,
        sales_rep_name=payload.sales_rep_name or user.full_name or "Sales Executive",
        notes=payload.notes
    )
    db.add(sale)

    # Accumulate client sales & revenue if not cancelled
    if sale.status != "cancelled":
        client.total_revenue += sale.amount
        client.order_count += 1
        client.next_reorder_date = sale_time + timedelta(days=client.reorder_cadence_days)

    audit = AuditLog(
        organization_id=org.id,
        actor_type="human_rep",
        actor_id=user.id,
        action="client_sale_logged",
        target_entity="client_sale",
        target_id=sale.id,
        payload={
            "client_id": client.id,
            "order_number": order_num,
            "amount": sale.amount,
            "new_client_total": client.total_revenue
        }
    )
    db.add(audit)

    await db.commit()
    await db.refresh(sale)
    return sale

@router.get("/clients/{client_id}/sales", response_model=List[ClientSaleResponse])
async def list_client_sales(
    client_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    client_stmt = select(ClientAccount).where(
        ClientAccount.id == client_id,
        ClientAccount.organization_id == org.id
    )
    client_res = await db.execute(client_stmt)
    if not client_res.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")

    sales_stmt = select(ClientSale).where(
        ClientSale.client_id == client_id,
        ClientSale.organization_id == org.id
    ).order_by(ClientSale.sale_date.desc())
    res = await db.execute(sales_stmt)
    return res.scalars().all()

@router.post("/leads/{lead_id}/convert-to-client", response_model=ClientAccountResponse)
async def convert_lead_to_client(
    lead_id: str,
    payload: LeadConversionPayload,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    user, org, _ = tenant_context

    stmt = select(Lead).options(
        selectinload(Lead.company),
        selectinload(Lead.contact)
    ).where(Lead.id == lead_id, Lead.organization_id == org.id)
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    # Update lead status to won/converted
    lead.pipeline_stage = "won"
    lead.status = "converted"

    now = datetime.now(timezone.utc)
    cadence = payload.reorder_cadence_days or 30

    # Check if client already exists for this company
    cl_stmt = select(ClientAccount).where(
        ClientAccount.organization_id == org.id,
        ClientAccount.company_id == lead.company_id
    )
    cl_res = await db.execute(cl_stmt)
    client = cl_res.scalar_one_or_none()

    if not client:
        client = ClientAccount(
            organization_id=org.id,
            company_id=lead.company_id,
            primary_contact_id=lead.contact_id,
            account_name=lead.company.name,
            account_tier=payload.account_tier or "standard",
            status="active",
            total_revenue=0.0,
            order_count=0,
            contract_start_date=now,
            renewal_date=now + timedelta(days=365),
            reorder_cadence_days=cadence,
            next_reorder_date=now + timedelta(days=cadence),
            account_manager=user.full_name or "Sales Director",
            notes=payload.notes or lead.notes or "Converted from Prospect Pipeline"
        )
        db.add(client)
        await db.flush()

    # Log initial deal / order if provided
    if payload.initial_order_amount and payload.initial_order_amount > 0:
        order_num = f"SO-{now.strftime('%Y%m%d')}-001"
        init_sale = ClientSale(
            organization_id=org.id,
            client_id=client.id,
            lead_id=lead.id,
            order_number=order_num,
            amount=payload.initial_order_amount,
            sale_date=now,
            status="completed",
            payment_method="credit_terms_30",
            items_summary=payload.initial_order_items or "Initial conversion contract order",
            sales_rep_name=user.full_name or "Sales Rep",
            notes="Initial closed deal from converted prospect lead"
        )
        db.add(init_sale)
        client.total_revenue += payload.initial_order_amount
        client.order_count += 1
        client.next_reorder_date = now + timedelta(days=client.reorder_cadence_days)

    audit = AuditLog(
        organization_id=org.id,
        actor_type="human_rep",
        actor_id=user.id,
        action="lead_converted_to_client",
        target_entity="client_account",
        target_id=client.id,
        payload={"lead_id": lead.id, "client_name": client.account_name}
    )
    db.add(audit)

    await db.commit()

    # Reload with relationships
    stmt = select(ClientAccount).options(
        selectinload(ClientAccount.company),
        selectinload(ClientAccount.primary_contact),
        selectinload(ClientAccount.sales)
    ).where(ClientAccount.id == client.id)
    out = await db.execute(stmt)
    return out.scalar_one()
