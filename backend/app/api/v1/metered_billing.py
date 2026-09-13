from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization
from app.schemas.metered_billing import (
    UsageRecordCreate,
    UsageBatchCreate,
    UsageRecordResponse,
    MeteredBillingSummaryResponse,
    SettleCycleRequest,
    MeteredInvoiceResponse,
    MetricCatalogItem
)
from app.services.metered_billing_service import MeteredBillingService

router = APIRouter(prefix="/metered-billing", tags=["Metered Usage Billing & Overages"])


@router.get("/catalog", response_model=List[MetricCatalogItem])
async def get_metric_catalog():
    """
    Returns the public and tenant reference catalog of supported billable metrics,
    tier included allowances, and per-unit overage rates.
    """
    return MeteredBillingService.get_metric_catalog()


@router.post("/usage", response_model=UsageRecordResponse, status_code=status.HTTP_201_CREATED)
async def record_usage(
    payload: UsageRecordCreate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingests a single metered usage event.
    Supports standard Bearer JWT or Developer API Key (`X-API-Key: jsp_live_...`).
    """
    _, org, _ = tenant_context
    try:
        record = await MeteredBillingService.record_usage(
            db=db,
            org_id=org.id,
            license_id=payload.license_id,
            metric_name=payload.metric_name,
            quantity=payload.quantity,
            idempotency_key=payload.idempotency_key,
            source=payload.source or "api_gateway",
            metadata=payload.metadata
        )
        return record
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/usage/batch", response_model=List[UsageRecordResponse], status_code=status.HTTP_201_CREATED)
async def batch_record_usage(
    payload: UsageBatchCreate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Ingests a batch of metered usage events for a license in a single transaction.
    """
    _, org, _ = tenant_context
    try:
        raw_events = [ev.model_dump() for ev in payload.events]
        records = await MeteredBillingService.batch_record_usage(
            db=db,
            org_id=org.id,
            license_id=payload.license_id,
            events=raw_events
        )
        return records
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/licenses/{license_id}/summary", response_model=MeteredBillingSummaryResponse)
async def get_license_meter_summary(
    license_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns real-time usage meters, tier allowances, accrued overages, and run-rate projections.
    """
    _, org, _ = tenant_context
    try:
        summary = await MeteredBillingService.get_meter_summary(
            db=db,
            license_id=license_id,
            org_id=org.id
        )
        return summary
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/licenses/{license_id}/settle", response_model=MeteredInvoiceResponse)
async def settle_billing_cycle(
    license_id: str,
    payload: SettleCycleRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Closes the current billing period, calculates overage charges, generates an itemized invoice,
    synchronizes with the client sales ledger, and triggers automatic card-on-file charging.
    """
    user, org, role = tenant_context
    if role not in ["admin", "super_admin", "sales_manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and billing managers can settle billing cycles"
        )
    try:
        invoice = await MeteredBillingService.settle_billing_cycle(
            db=db,
            license_id=license_id,
            org=org,
            user=user,
            auto_charge=payload.auto_charge,
            notes=payload.notes
        )
        # Format response
        client_name = invoice.client.account_name if invoice.client else None
        return MeteredInvoiceResponse(
            id=invoice.id,
            invoice_number=invoice.invoice_number,
            license_id=invoice.license_id,
            client_id=invoice.client_id,
            client_name=client_name,
            cycle_start=invoice.cycle_start,
            cycle_end=invoice.cycle_end,
            status=invoice.status,
            line_items=invoice.line_items,
            subtotal_overage_amount=invoice.subtotal_overage_amount,
            tax_amount=invoice.tax_amount,
            total_billed_amount=invoice.total_billed_amount,
            payment_method=invoice.payment_method,
            payment_status=invoice.payment_status,
            client_sale_id=invoice.client_sale_id,
            settled_at=invoice.settled_at,
            notes=invoice.notes
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/invoices", response_model=List[MeteredInvoiceResponse])
async def list_invoices(
    license_id: Optional[str] = Query(None),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Lists historical metered billing invoices for the tenant.
    """
    _, org, _ = tenant_context
    invoices = await MeteredBillingService.list_invoices(
        db=db,
        org_id=org.id,
        license_id=license_id
    )
    result = []
    for inv in invoices:
        result.append(
            MeteredInvoiceResponse(
                id=inv.id,
                invoice_number=inv.invoice_number,
                license_id=inv.license_id,
                client_id=inv.client_id,
                client_name=inv.client.account_name if inv.client else None,
                cycle_start=inv.cycle_start,
                cycle_end=inv.cycle_end,
                status=inv.status,
                line_items=inv.line_items,
                subtotal_overage_amount=inv.subtotal_overage_amount,
                tax_amount=inv.tax_amount,
                total_billed_amount=inv.total_billed_amount,
                payment_method=inv.payment_method,
                payment_status=inv.payment_status,
                client_sale_id=inv.client_sale_id,
                settled_at=inv.settled_at,
                notes=inv.notes
            )
        )
    return result


@router.get("/invoices/{invoice_id}", response_model=MeteredInvoiceResponse)
async def get_invoice(
    invoice_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieves a single metered billing invoice with line item details.
    """
    _, org, _ = tenant_context
    inv = await MeteredBillingService.get_invoice(
        db=db,
        invoice_id=invoice_id,
        org_id=org.id
    )
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return MeteredInvoiceResponse(
        id=inv.id,
        invoice_number=inv.invoice_number,
        license_id=inv.license_id,
        client_id=inv.client_id,
        client_name=inv.client.account_name if inv.client else None,
        cycle_start=inv.cycle_start,
        cycle_end=inv.cycle_end,
        status=inv.status,
        line_items=inv.line_items,
        subtotal_overage_amount=inv.subtotal_overage_amount,
        tax_amount=inv.tax_amount,
        total_billed_amount=inv.total_billed_amount,
        payment_method=inv.payment_method,
        payment_status=inv.payment_status,
        client_sale_id=inv.client_sale_id,
        settled_at=inv.settled_at,
        notes=inv.notes
    )
