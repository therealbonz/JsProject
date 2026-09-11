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
from app.models.crm import Company, Contact, Lead, Product, KnowledgeDocument, CallLog, ClientAccount, ClientSale, Appointment
from app.models.procurement import PurchaseOrder
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
    LeadConversionPayload,
    AppointmentCreate, AppointmentUpdate, AppointmentResponse,
    AttachPaymentMethodRequest, AutoChargeToggleRequest, SetupPaymentMethodResponse
)
from app.services.stripe_recurring_service import StripeRecurringService
from app.services.notification_service import NotificationService
from app.services.replenishment_service import ReplenishmentService
import logging
from app.services.order_filler.agent import OrderFillerAgent
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)

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
        selectinload(Lead.call_logs),
        selectinload(Lead.appointments)
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
        selectinload(Lead.call_logs),
        selectinload(Lead.appointments)
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
        selectinload(Lead.call_logs),
        selectinload(Lead.appointments)
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
        selectinload(Lead.call_logs),
        selectinload(Lead.appointments)
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

@router.post("/clients/{client_id}/payment-method/attach", response_model=ClientAccountResponse)
async def attach_client_payment_method(
    client_id: str,
    payload: AttachPaymentMethodRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Attaches a payment method (card or ACH) on file for the client account
    and enables/configures off-session auto-billing.
    """
    user, org, _ = tenant_context
    stmt = (
        select(ClientAccount)
        .options(
            selectinload(ClientAccount.company),
            selectinload(ClientAccount.primary_contact),
            selectinload(ClientAccount.sales)
        )
        .where(ClientAccount.id == client_id, ClientAccount.organization_id == org.id)
    )
    res = await db.execute(stmt)
    client = res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")

    updated_client = await StripeRecurringService.attach_payment_method(
        db=db,
        client=client,
        card_brand=payload.card_brand or "visa",
        card_last4=payload.card_last4 or "4242",
        payment_method_type=payload.payment_method_type or "card",
        enable_auto_charge=payload.enable_auto_charge if payload.enable_auto_charge is not None else True,
        auto_charge_limit=payload.auto_charge_limit
    )
    return updated_client

@router.delete("/clients/{client_id}/payment-method", response_model=ClientAccountResponse)
async def detach_client_payment_method(
    client_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Removes the stored payment method on file and disables automatic charging.
    """
    user, org, _ = tenant_context
    stmt = (
        select(ClientAccount)
        .options(
            selectinload(ClientAccount.company),
            selectinload(ClientAccount.primary_contact),
            selectinload(ClientAccount.sales)
        )
        .where(ClientAccount.id == client_id, ClientAccount.organization_id == org.id)
    )
    res = await db.execute(stmt)
    client = res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")

    updated_client = await StripeRecurringService.detach_payment_method(db=db, client=client)
    return updated_client

@router.post("/clients/{client_id}/payment-method/auto-charge", response_model=ClientAccountResponse)
async def toggle_client_auto_charge(
    client_id: str,
    payload: AutoChargeToggleRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Toggles automatic charge authorization and adjusts safety spending cap.
    """
    user, org, _ = tenant_context
    stmt = (
        select(ClientAccount)
        .options(
            selectinload(ClientAccount.company),
            selectinload(ClientAccount.primary_contact),
            selectinload(ClientAccount.sales)
        )
        .where(ClientAccount.id == client_id, ClientAccount.organization_id == org.id)
    )
    res = await db.execute(stmt)
    client = res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")

    enabled = payload.auto_charge_enabled if payload.auto_charge_enabled is not None else (payload.enabled if payload.enabled is not None else True)
    limit = payload.auto_charge_limit if payload.auto_charge_limit is not None else payload.limit

    updated_client = await StripeRecurringService.toggle_auto_charge(
        db=db,
        client=client,
        enabled=enabled,
        limit=limit
    )
    return updated_client

@router.post("/clients/{client_id}/charge-sale/{sale_id}")
async def charge_client_stored_card_for_sale(
    client_id: str,
    sale_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Manually or programmatically triggers an off-session charge against the stored card
    on file for a specific unpaid order, automatically advancing cadence and triggering fulfillment.
    """
    user, org, _ = tenant_context
    stmt = (
        select(ClientAccount)
        .options(
            selectinload(ClientAccount.company),
            selectinload(ClientAccount.primary_contact)
        )
        .where(ClientAccount.id == client_id, ClientAccount.organization_id == org.id)
    )
    res = await db.execute(stmt)
    client = res.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client account not found")

    sale_stmt = (
        select(ClientSale)
        .options(selectinload(ClientSale.purchase_orders))
        .where(ClientSale.id == sale_id, ClientSale.client_id == client.id, ClientSale.organization_id == org.id)
    )
    sale_res = await db.execute(sale_stmt)
    sale = sale_res.scalar_one_or_none()
    if not sale:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sale not found for this client")

    charge_result = await StripeRecurringService.charge_stored_payment_method(
        db=db,
        client=client,
        sale=sale,
        org=org
    )
    if not charge_result.get("success"):
        raise HTTPException(status_code=400, detail=charge_result.get("error", "Charge failed"))

    # Advance client replenishment cadence
    await ReplenishmentService.advance_client_cadence_on_payment(db=db, sale=sale)
    await db.commit()

    # Dispatch Payment Received notification
    await NotificationService.create_and_send_notification(
        db=db,
        sale=sale,
        event_type="payment_received",
        channel="email"
    )

    # If auto-fulfill enabled, trigger dropshipping PO
    auto_fulfilled = False
    po_data = None
    if sale.auto_fulfill_on_payment and not sale.purchase_orders:
        dest_address = None
        if client.company and client.company.address:
            dest_address = client.company.address
        else:
            dest_address = f"{client.account_name} Receiving Dock"

        agent = OrderFillerAgent()
        po_res = await agent.auto_fill_order(
            db=db,
            org_id=sale.organization_id,
            prompt=sale.items_summary,
            max_budget_limit=max(sale.amount * 1.5, 2000.0),
            client_sale_id=sale.id,
            destination_type="customer_dropship",
            destination_address=dest_address
        )
        auto_fulfilled = True
        po_data = {
            "po_number": po_res.get("po_number"),
            "carrier": po_res.get("carrier"),
            "tracking_number": po_res.get("tracking_number")
        }

    return {
        "success": True,
        "sale_id": sale.id,
        "order_number": sale.order_number,
        "payment_status": sale.payment_status,
        "charge": charge_result,
        "auto_fulfilled": auto_fulfilled,
        "fulfillment": po_data
    }

@router.post("/clients/{client_id}/sales", response_model=ClientSaleResponse)
async def log_client_sale(
    client_id: str,
    payload: ClientSaleCreate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    user, org, _ = tenant_context

    stmt = select(ClientAccount).options(
        selectinload(ClientAccount.primary_contact)
    ).where(
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
        payment_status=payload.payment_status or "unpaid",
        customer_email=str(payload.customer_email) if payload.customer_email else (client.primary_contact.email if client.primary_contact else None),
        customer_phone=payload.customer_phone or (client.primary_contact.phone if client.primary_contact else None),
        auto_fulfill_on_payment=payload.auto_fulfill_on_payment if payload.auto_fulfill_on_payment is not None else True,
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

    # Dispatch outbound order.created webhook
    try:
        await WebhookService.dispatch_event(
            db=db,
            org_id=org.id,
            event_name="order.created",
            payload={
                "sale_id": sale.id,
                "order_number": sale.order_number,
                "amount": sale.amount,
                "client_id": client.id,
                "client_name": client.account_name,
                "status": sale.status,
                "payment_status": sale.payment_status,
                "created_at": sale.created_at.isoformat() if sale.created_at else now.isoformat()
            }
        )
    except Exception as wh_err:
        logger.warning(f"Failed to dispatch order.created webhook: {wh_err}")

    return sale

@router.get("/sales", response_model=List[ClientSaleResponse])
@router.get("/clients/all-sales", response_model=List[ClientSaleResponse])
async def list_all_tenant_sales(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    sales_stmt = select(ClientSale).options(
        selectinload(ClientSale.purchase_orders).selectinload(PurchaseOrder.shipments)
    ).where(
        ClientSale.organization_id == org.id
    ).order_by(ClientSale.sale_date.desc())
    res = await db.execute(sales_stmt)
    sales = res.scalars().all()

    output = []
    for s in sales:
        po = s.purchase_orders[0] if s.purchase_orders else None
        ship = po.shipments[0] if (po and po.shipments) else None
        output.append({
            "id": s.id,
            "organization_id": s.organization_id,
            "client_id": s.client_id,
            "lead_id": s.lead_id,
            "order_number": s.order_number,
            "amount": s.amount,
            "sale_date": s.sale_date,
            "status": s.status,
            "payment_method": s.payment_method,
            "payment_status": s.payment_status or "unpaid",
            "stripe_checkout_url": s.stripe_checkout_url,
            "stripe_session_id": s.stripe_session_id,
            "customer_email": s.customer_email,
            "customer_phone": s.customer_phone,
            "auto_fulfill_on_payment": s.auto_fulfill_on_payment,
            "items_summary": s.items_summary,
            "sales_rep_name": s.sales_rep_name,
            "notes": s.notes,
            "purchase_order_id": po.id if po else None,
            "po_number": po.po_number if po else None,
            "carrier": ship.carrier if ship else None,
            "tracking_number": ship.tracking_number if ship else None,
            "tracking_url": ship.tracking_url if ship else None,
            "shipping_status": ship.current_status if ship else (po.status if po else None),
            "destination_type": po.destination_type if po else None,
            "created_at": s.created_at
        })
    return output

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

    sales_stmt = select(ClientSale).options(
        selectinload(ClientSale.purchase_orders).selectinload(PurchaseOrder.shipments)
    ).where(
        ClientSale.client_id == client_id,
        ClientSale.organization_id == org.id
    ).order_by(ClientSale.sale_date.desc())
    res = await db.execute(sales_stmt)
    sales = res.scalars().all()

    output = []
    for s in sales:
        po = s.purchase_orders[0] if s.purchase_orders else None
        ship = po.shipments[0] if (po and po.shipments) else None
        output.append({
            "id": s.id,
            "organization_id": s.organization_id,
            "client_id": s.client_id,
            "lead_id": s.lead_id,
            "order_number": s.order_number,
            "amount": s.amount,
            "sale_date": s.sale_date,
            "status": s.status,
            "payment_method": s.payment_method,
            "payment_status": s.payment_status or "unpaid",
            "stripe_checkout_url": s.stripe_checkout_url,
            "stripe_session_id": s.stripe_session_id,
            "customer_email": s.customer_email,
            "customer_phone": s.customer_phone,
            "auto_fulfill_on_payment": s.auto_fulfill_on_payment,
            "items_summary": s.items_summary,
            "sales_rep_name": s.sales_rep_name,
            "notes": s.notes,
            "purchase_order_id": po.id if po else None,
            "po_number": po.po_number if po else None,
            "carrier": ship.carrier if ship else None,
            "tracking_number": ship.tracking_number if ship else None,
            "tracking_url": ship.tracking_url if ship else None,
            "shipping_status": ship.current_status if ship else (po.status if po else None),
            "destination_type": po.destination_type if po else None,
            "created_at": s.created_at
        })
    return output

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
        order_num = f"SO-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:4].upper()}"
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

# -------------------------------------------------------------
# Appointments & Closer Scheduling
# -------------------------------------------------------------
@router.get("/appointments", response_model=List[AppointmentResponse])
async def list_appointments(
    lead_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(Appointment).options(
        selectinload(Appointment.company),
        selectinload(Appointment.contact)
    ).where(Appointment.organization_id == org.id)

    if lead_id:
        stmt = stmt.where(Appointment.lead_id == lead_id)
    if status:
        stmt = stmt.where(Appointment.status == status)

    stmt = stmt.order_by(Appointment.scheduled_at.asc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/appointments", response_model=AppointmentResponse)
async def create_appointment(
    payload: AppointmentCreate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    user, org, _ = tenant_context

    # Verify lead exists in this organization
    lead_stmt = select(Lead).where(Lead.id == payload.lead_id, Lead.organization_id == org.id)
    lead_res = await db.execute(lead_stmt)
    lead = lead_res.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    meeting_url = payload.meeting_url or f"https://meet.google.com/agy-{str(uuid.uuid4())[:8]}"

    appointment = Appointment(
        organization_id=org.id,
        lead_id=lead.id,
        company_id=payload.company_id or lead.company_id,
        contact_id=payload.contact_id or lead.contact_id,
        title=payload.title or "Executive Procurement Consultation",
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes or 30,
        status=payload.status or "scheduled",
        meeting_url=meeting_url,
        closer_name=payload.closer_name or user.full_name or "Senior Sales Executive",
        closer_email=payload.closer_email or user.email,
        executive_briefing=payload.executive_briefing or {},
        notes=payload.notes,
        booked_by_agent=payload.booked_by_agent if payload.booked_by_agent is not None else False
    )
    db.add(appointment)

    # Automatically advance lead pipeline stage if active
    if lead.pipeline_stage in ["new", "researching", "ready_contact", "contacted", "connected"]:
        lead.pipeline_stage = "qualified"
        lead.next_action_at = payload.scheduled_at
        lead.next_action_type = "scheduled_closer_call"

    audit = AuditLog(
        organization_id=org.id,
        actor_type="human_rep" if not payload.booked_by_agent else "ai_agent",
        actor_id=user.id,
        action="appointment_created",
        target_entity="appointment",
        target_id=appointment.id,
        payload={
            "lead_id": lead.id,
            "scheduled_at": payload.scheduled_at.isoformat(),
            "closer_name": appointment.closer_name
        }
    )
    db.add(audit)
    await db.commit()

    # Reload with relationships
    stmt = select(Appointment).options(
        selectinload(Appointment.company),
        selectinload(Appointment.contact)
    ).where(Appointment.id == appointment.id)
    res = await db.execute(stmt)
    return res.scalar_one()

@router.get("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def get_appointment(
    appointment_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(Appointment).options(
        selectinload(Appointment.company),
        selectinload(Appointment.contact)
    ).where(Appointment.id == appointment_id, Appointment.organization_id == org.id)
    result = await db.execute(stmt)
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    return appointment

@router.patch("/appointments/{appointment_id}", response_model=AppointmentResponse)
async def update_appointment(
    appointment_id: str,
    payload: AppointmentUpdate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    user, org, _ = tenant_context
    stmt = select(Appointment).options(
        selectinload(Appointment.company),
        selectinload(Appointment.contact)
    ).where(Appointment.id == appointment_id, Appointment.organization_id == org.id)
    result = await db.execute(stmt)
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    if payload.title is not None:
        appointment.title = payload.title
    if payload.scheduled_at is not None:
        appointment.scheduled_at = payload.scheduled_at
    if payload.duration_minutes is not None:
        appointment.duration_minutes = payload.duration_minutes
    if payload.status is not None:
        appointment.status = payload.status
    if payload.meeting_url is not None:
        appointment.meeting_url = payload.meeting_url
    if payload.closer_name is not None:
        appointment.closer_name = payload.closer_name
    if payload.closer_email is not None:
        appointment.closer_email = payload.closer_email
    if payload.executive_briefing is not None:
        appointment.executive_briefing = payload.executive_briefing
    if payload.notes is not None:
        appointment.notes = payload.notes

    audit = AuditLog(
        organization_id=org.id,
        actor_type="human_rep",
        actor_id=user.id,
        action="appointment_updated",
        target_entity="appointment",
        target_id=appointment.id,
        payload={"status": appointment.status, "scheduled_at": appointment.scheduled_at.isoformat()}
    )
    db.add(audit)
    await db.commit()

    return appointment

@router.delete("/appointments/{appointment_id}")
async def delete_appointment(
    appointment_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    user, org, _ = tenant_context
    stmt = select(Appointment).where(Appointment.id == appointment_id, Appointment.organization_id == org.id)
    result = await db.execute(stmt)
    appointment = result.scalar_one_or_none()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    audit = AuditLog(
        organization_id=org.id,
        actor_type="human_rep",
        actor_id=user.id,
        action="appointment_deleted",
        target_entity="appointment",
        target_id=appointment.id,
        payload={"title": appointment.title, "lead_id": appointment.lead_id}
    )
    db.add(audit)
    await db.delete(appointment)
    await db.commit()
    return {"status": "deleted", "id": appointment_id}
