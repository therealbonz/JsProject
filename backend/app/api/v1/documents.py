import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.tenant import Organization
from app.models.crm import ClientSale, ClientAccount
from app.models.procurement import PurchaseOrder, ShipmentTracking
from app.services.document_service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Printable Documents & Logistics Telemetry"])

@router.get("/invoice/{identifier}", response_class=HTMLResponse)
async def get_printable_invoice(
    identifier: str,
    request: Request,
    auto_print: bool = Query(False, alias="print"),
    db: AsyncSession = Depends(get_db)
):
    """
    Renders a white-labeled, print-ready B2B commercial invoice with scannable payment/tracking QR code telemetry.
    Accepts sale ID or order number (e.g. SO-...).
    """
    stmt = (
        select(ClientSale)
        .options(
            selectinload(ClientSale.client).selectinload(ClientAccount.primary_contact),
            selectinload(ClientSale.client).selectinload(ClientAccount.company)
        )
        .where(or_(ClientSale.id == identifier, ClientSale.order_number == identifier))
    )
    res = await db.execute(stmt)
    sale = res.scalar_one_or_none()

    if not sale:
        raise HTTPException(status_code=404, detail="Order or invoice not found")

    # Fetch organization branding
    org = None
    if sale.organization_id:
        org_stmt = select(Organization).where(Organization.id == sale.organization_id)
        org_res = await db.execute(org_stmt)
        org = org_res.scalar_one_or_none()

    base_url = str(request.base_url).rstrip("/")
    # If request is coming through reverse proxy or custom domain
    if "therealbonz.com" in str(request.headers.get("host", "")):
        base_url = "https://therealbonz.com/JsProject"

    html = DocumentService.render_invoice_html(
        sale=sale,
        org=org,
        base_url=base_url,
        auto_print=auto_print
    )
    return HTMLResponse(content=html)


@router.get("/packing-slip/{identifier}", response_class=HTMLResponse)
async def get_printable_packing_slip(
    identifier: str,
    request: Request,
    auto_print: bool = Query(False, alias="print"),
    db: AsyncSession = Depends(get_db)
):
    """
    Renders a warehouse fulfillment packing slip & pick list with scannable logistics telemetry QR code.
    Accepts sale ID or order number (e.g. SO-...).
    """
    stmt = (
        select(ClientSale)
        .options(
            selectinload(ClientSale.client),
            selectinload(ClientSale.purchase_orders).selectinload(PurchaseOrder.shipments)
        )
        .where(or_(ClientSale.id == identifier, ClientSale.order_number == identifier))
    )
    res = await db.execute(stmt)
    sale = res.scalar_one_or_none()

    if not sale:
        raise HTTPException(status_code=404, detail="Order or packing slip not found")

    # Fetch organization branding
    org = None
    if sale.organization_id:
        org_stmt = select(Organization).where(Organization.id == sale.organization_id)
        org_res = await db.execute(org_stmt)
        org = org_res.scalar_one_or_none()

    base_url = str(request.base_url).rstrip("/")
    if "therealbonz.com" in str(request.headers.get("host", "")):
        base_url = "https://therealbonz.com/JsProject"

    html = DocumentService.render_packing_slip_html(
        sale=sale,
        org=org,
        base_url=base_url,
        auto_print=auto_print
    )
    return HTMLResponse(content=html)
