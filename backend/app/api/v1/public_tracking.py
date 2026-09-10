from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.tenant import Organization
from app.models.crm import ClientSale, ClientAccount
from app.models.procurement import PurchaseOrder, ShipmentTracking
from app.schemas.public_tracking import PublicOrderTrackingResponse

router = APIRouter(prefix="/public/tracking", tags=["Public Order Tracking"])

@router.get("/{order_number}", response_model=PublicOrderTrackingResponse)
async def get_public_order_tracking(
    order_number: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Public sanitized order tracking endpoint for customers.
    Excludes internal supplier purchasing costs, PO numbers, and profit margins.
    """
    stmt = (
        select(ClientSale)
        .options(
            selectinload(ClientSale.client).selectinload(ClientAccount.company),
            selectinload(ClientSale.purchase_orders).selectinload(PurchaseOrder.shipments)
        )
        .where(ClientSale.order_number == order_number)
    )
    result = await db.execute(stmt)
    sale = result.scalar_one_or_none()

    if not sale:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_number}' not found. Please verify the order number."
        )

    # Determine shipping details
    po = sale.purchase_orders[0] if sale.purchase_orders else None
    shipment = po.shipments[0] if (po and po.shipments) else None

    # Delivery address resolution
    delivery_address = None
    if po and po.destination_address:
        delivery_address = po.destination_address
    elif sale.client and sale.client.company and sale.client.company.address:
        delivery_address = sale.client.company.address
    elif sale.client:
        delivery_address = f"{sale.client.account_name} Receiving Facility"

    # Status calculation
    stage_pcts = {
        "label_created": 20,
        "picked_up": 40,
        "in_transit": 60,
        "out_for_delivery": 80,
        "delivered": 100
    }

    carrier = shipment.carrier if shipment else (po.carrier if po else None)
    tracking_number = shipment.tracking_number if shipment else (po.tracking_number if po else None)
    tracking_url = shipment.tracking_url if shipment else (po.tracking_url if po else None)

    if shipment:
        current_status = shipment.current_status
        shipping_stage_pct = stage_pcts.get(shipment.current_status, 30)
        history_events = shipment.history_events or []
        is_delivered = (shipment.current_status == "delivered")
    elif po:
        if po.status == "delivered":
            current_status = "delivered"
            shipping_stage_pct = 100
            is_delivered = True
        elif po.status in ("in_transit", "shipped"):
            current_status = "in_transit"
            shipping_stage_pct = 60
            is_delivered = False
        else:
            current_status = "processing"
            shipping_stage_pct = 20
            is_delivered = False
        history_events = []
    else:
        if sale.status == "completed":
            current_status = "delivered"
            shipping_stage_pct = 100
            is_delivered = True
        elif sale.payment_status == "unpaid":
            current_status = "awaiting_payment"
            shipping_stage_pct = 10
            is_delivered = False
        else:
            current_status = "processing"
            shipping_stage_pct = 20
            is_delivered = False
        history_events = []

    # Retrieve Organization branding if available
    org = None
    if sale.organization_id:
        org_res = await db.execute(select(Organization).where(Organization.id == sale.organization_id))
        org = org_res.scalar_one_or_none()

    brand_name = (org.brand_name or org.name) if org else "Order Bot Distribution"
    brand_logo_url = org.brand_logo_url if org else None
    brand_accent_color = (org.brand_accent_color or "#4f46e5") if org else "#4f46e5"
    support_email = (org.support_email or "support@therealbonz.com") if org else "support@therealbonz.com"
    support_phone = org.support_phone if org else None
    custom_footer_text = org.custom_footer_text if org else None
    tracking_portal_notice = org.tracking_portal_notice if org else None

    return PublicOrderTrackingResponse(
        order_number=sale.order_number,
        client_name=sale.client.account_name if sale.client else "Client Customer",
        delivery_address=delivery_address,
        items_summary=sale.items_summary,
        sale_date=sale.sale_date,
        payment_status=sale.payment_status,
        carrier=carrier,
        tracking_number=tracking_number,
        tracking_url=tracking_url,
        current_status=current_status,
        shipping_stage_pct=shipping_stage_pct,
        is_delivered=is_delivered,
        destination_type=po.destination_type if po else "customer_dropship",
        history_events=history_events,
        stripe_checkout_url=sale.stripe_checkout_url,
        brand_name=brand_name,
        brand_logo_url=brand_logo_url,
        brand_accent_color=brand_accent_color,
        support_email=support_email,
        support_phone=support_phone,
        custom_footer_text=custom_footer_text,
        tracking_portal_notice=tracking_portal_notice,
    )
