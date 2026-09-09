import random
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.api.deps import get_current_tenant
from app.models.tenant import User, Organization
from app.models.procurement import Supplier, PurchaseOrder, ShipmentTracking, InventoryItem
from app.models.crm import ClientSale, ClientAccount
from app.schemas.procurement import (
    SupplierCreate, SupplierResponse,
    PurchaseOrderCreate, PurchaseOrderResponse, AutoFillOrderRequest,
    ShipmentTrackingBrief, ShipmentAdvanceRequest, DispatchShipmentRequest,
    ProcurementStatsResponse
)
from app.services.order_filler.agent import order_filler_agent

router = APIRouter(prefix="/fulfillment", tags=["Order Fulfillment & Supply Chain"])

@router.get("/suppliers", response_model=List[SupplierResponse])
async def list_suppliers(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    await order_filler_agent.ensure_default_suppliers(db, org.id)
    stmt = select(Supplier).where(Supplier.organization_id == org.id).order_by(Supplier.created_at.asc())
    result = await db.execute(stmt)
    return result.scalars().all()

@router.post("/suppliers", response_model=SupplierResponse)
async def create_supplier(
    payload: SupplierCreate,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    supplier = Supplier(
        organization_id=org.id,
        name=payload.name,
        code=payload.code.lower().replace(" ", "_"),
        website_url=payload.website_url,
        adapter_type=payload.adapter_type,
        status=payload.status,
        category=payload.category,
        lead_days_estimate=payload.lead_days_estimate,
        auth_config=payload.auth_config,
        notes=payload.notes
    )
    db.add(supplier)
    await db.commit()
    await db.refresh(supplier)
    return supplier

@router.post("/autofill")
async def autofill_order(
    payload: AutoFillOrderRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    result = await order_filler_agent.auto_fill_order(
        db=db,
        org_id=org.id,
        prompt=payload.requirement_prompt,
        preferred_supplier_code=payload.preferred_supplier_code,
        destination_type=payload.destination_type,
        destination_address=payload.destination_address,
        client_sale_id=payload.client_sale_id,
        max_budget_limit=payload.max_budget_limit or 500.0
    )
    return result

@router.get("/orders", response_model=List[PurchaseOrderResponse])
async def list_purchase_orders(
    status_filter: Optional[str] = Query(None),
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(PurchaseOrder).options(
        selectinload(PurchaseOrder.supplier),
        selectinload(PurchaseOrder.shipments),
        selectinload(PurchaseOrder.client_sale).selectinload(ClientSale.client)
    ).where(PurchaseOrder.organization_id == org.id)

    if status_filter:
        stmt = stmt.where(PurchaseOrder.status == status_filter)

    stmt = stmt.order_by(desc(PurchaseOrder.created_at))
    res = await db.execute(stmt)
    orders = res.scalars().all()

    # Enrich supplier_name, client sale details, margins, and shipping success status
    output = []
    for o in orders:
        sale = o.client_sale
        client_order_num = sale.order_number if sale else None
        client_name = (sale.client.account_name if (sale and sale.client) else None)
        client_sale_amt = sale.amount if sale else None

        profit_margin = round(sale.amount - o.total_cost, 2) if sale else None
        profit_margin_pct = round(((sale.amount - o.total_cost) / sale.amount * 100), 1) if (sale and sale.amount > 0) else None

        # Determine order bot shipping success milestone & progress percentage
        shipping_status = "Order Placed"
        stage_pct = 20
        if o.shipments:
            latest_ship = o.shipments[0]
            st = latest_ship.current_status
            if st == "delivered" or o.status == "delivered":
                shipping_status = "Complete Success (Delivered)"
                stage_pct = 100
            elif st == "out_for_delivery":
                shipping_status = "Out for Delivery"
                stage_pct = 80
            elif st == "in_transit":
                shipping_status = "In Transit"
                stage_pct = 60
            elif st == "picked_up":
                shipping_status = "Carrier Picked Up"
                stage_pct = 40
            elif st == "label_created":
                shipping_status = "Label Created / Dispatched"
                stage_pct = 25
        elif o.status == "delivered":
            shipping_status = "Complete Success (Delivered)"
            stage_pct = 100
        elif o.status == "pending_approval":
            shipping_status = "Pending HITL Approval"
            stage_pct = 10
        elif o.status == "ordered":
            shipping_status = "Purchased / Ordered"
            stage_pct = 20

        data = {
            "id": o.id,
            "po_number": o.po_number,
            "supplier_id": o.supplier_id,
            "client_sale_id": o.client_sale_id,
            "total_cost": o.total_cost,
            "currency": o.currency,
            "status": o.status,
            "requires_approval": o.requires_approval,
            "approved_by": o.approved_by,
            "approval_reason": o.approval_reason,
            "items_json": o.items_json,
            "confirmation_code": o.confirmation_code,
            "placed_at": o.placed_at,
            "ordered_by_agent": o.ordered_by_agent,
            "destination_type": o.destination_type,
            "destination_address": o.destination_address,
            "notes": o.notes,
            "supplier_name": o.supplier.name if o.supplier else "Direct Vendor",
            "client_sale_order_number": client_order_num,
            "client_name": client_name,
            "client_sale_amount": client_sale_amt,
            "profit_margin_dollars": profit_margin,
            "profit_margin_pct": profit_margin_pct,
            "shipping_success_status": shipping_status,
            "shipping_stage_pct": stage_pct,
            "shipments": [ShipmentTrackingBrief.model_validate(s) for s in o.shipments],
            "created_at": o.created_at,
            "updated_at": o.updated_at
        }
        output.append(data)
    return output

@router.post("/orders/{po_id}/approve")
async def approve_purchase_order(
    po_id: str,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    user, org, _ = tenant_context
    stmt = select(PurchaseOrder).options(selectinload(PurchaseOrder.supplier)).where(
        PurchaseOrder.id == po_id,
        PurchaseOrder.organization_id == org.id
    )
    res = await db.execute(stmt)
    po = res.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    if not po.requires_approval and po.status != "pending_approval":
        return {"message": "Order is already approved/executed.", "status": po.status}

    # Execute order via adapter
    adapter = order_filler_agent.get_adapter_for_supplier(po.supplier)
    dest_str = po.destination_address or "Main Fulfillment Warehouse (Bay 4)"
    order_result = await adapter.place_order(po.items_json, shipping_address=dest_str)

    po.status = "ordered"
    po.requires_approval = False
    po.approved_by = user.email
    po.confirmation_code = order_result.get("order_confirmation")
    po.notes = (po.notes or "") + f" | Approved by {user.email} at {datetime.now(timezone.utc).isoformat()}"

    # Create shipment tracking
    carrier = order_result.get("carrier", "UPS")
    tracking_num = order_result.get("initial_tracking_number", f"1Z{random.randint(10000000, 99999999)}")
    now_iso = datetime.now(timezone.utc).isoformat()

    shipment = ShipmentTracking(
        organization_id=org.id,
        purchase_order_id=po.id,
        carrier=carrier,
        tracking_number=tracking_num,
        tracking_url=f"https://www.google.com/search?q={carrier}+tracking+{tracking_num}",
        current_status="label_created",
        origin=f"{po.supplier.name} Fulfillment Center",
        destination=dest_str,
        estimated_delivery=datetime.now(timezone.utc) + timedelta(days=order_result.get("estimated_delivery_days", 2)),
        history_events=[
            {
                "timestamp": now_iso,
                "status": "label_created",
                "location": f"{po.supplier.name} Fulfillment Center",
                "description": f"Manager approval granted by {user.email}. Supplier order placed. Tracking {tracking_num} generated."
            }
        ]
    )
    db.add(shipment)

    # In-transit stock
    for it in (po.items_json or []):
        inv_stmt = select(InventoryItem).where(InventoryItem.organization_id == org.id, InventoryItem.sku == it.get("sku"))
        inv_res = await db.execute(inv_stmt)
        inv_item = inv_res.scalar_one_or_none()
        if inv_item:
            inv_item.quantity_in_transit += it.get("qty", 0)

    await db.commit()
    return {
        "success": True,
        "message": f"PO {po.po_number} approved and executed.",
        "confirmation_code": po.confirmation_code,
        "tracking_number": tracking_num,
        "carrier": carrier
    }

@router.get("/shipments", response_model=List[ShipmentTrackingBrief])
async def list_shipments(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    stmt = select(ShipmentTracking).where(ShipmentTracking.organization_id == org.id).order_by(desc(ShipmentTracking.created_at))
    res = await db.execute(stmt)
    return res.scalars().all()

@router.post("/shipments/{tracking_id}/advance")
async def advance_shipment(
    tracking_id: str,
    payload: ShipmentAdvanceRequest = None,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    note = payload.custom_note if payload else None
    tracking = await order_filler_agent.advance_shipment_milestone(db, tracking_id, custom_note=note)
    return {
        "success": True,
        "current_status": tracking.current_status,
        "carrier": tracking.carrier,
        "tracking_number": tracking.tracking_number,
        "events_count": len(tracking.history_events or [])
    }

@router.post("/shipments/dispatch")
async def dispatch_outbound_shipment(
    payload: DispatchShipmentRequest,
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    """
    Dispatches purchased inventory outbound to a destination client or subsidiary facility.
    Generates outbound carrier shipping manifest and tracking record.
    """
    user, org, _ = tenant_context
    po_stmt = select(PurchaseOrder).where(PurchaseOrder.id == payload.purchase_order_id, PurchaseOrder.organization_id == org.id)
    po_res = await db.execute(po_stmt)
    po = po_res.scalar_one_or_none()
    if not po:
        raise HTTPException(status_code=404, detail="Purchase Order not found")

    carrier = payload.carrier.upper()
    prefix = "1Z" if carrier == "UPS" else ("77" if carrier == "FEDEX" else "94")
    outbound_trk = f"{prefix}{random.randint(10000000, 99999999)}"
    now_iso = datetime.now(timezone.utc).isoformat()

    outbound_shipment = ShipmentTracking(
        organization_id=org.id,
        purchase_order_id=po.id,
        carrier=carrier,
        tracking_number=outbound_trk,
        tracking_url=f"https://www.google.com/search?q={carrier}+tracking+{outbound_trk}",
        current_status="label_created",
        origin="Main Warehouse - Outbound Freight Dock",
        destination=payload.destination,
        estimated_delivery=datetime.now(timezone.utc) + timedelta(days=2),
        history_events=[
            {
                "timestamp": now_iso,
                "status": "label_created",
                "location": "Outbound Shipping Dock",
                "description": f"Outbound dispatch manifest generated by {user.email}. Dispatched to destination: {payload.destination}."
            }
        ]
    )
    db.add(outbound_shipment)
    if payload.client_sale_id:
        po.client_sale_id = payload.client_sale_id
    po.destination_type = "customer_dropship"
    po.destination_address = payload.destination
    po.status = "shipped"

    await db.commit()
    return {
        "success": True,
        "message": f"Inventory from PO {po.po_number} dispatched.",
        "carrier": carrier,
        "tracking_number": outbound_trk,
        "destination": payload.destination
    }

@router.get("/stats", response_model=ProcurementStatsResponse)
async def get_procurement_stats(
    tenant_context: tuple[User, Organization, str] = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db)
):
    _, org, _ = tenant_context
    await order_filler_agent.ensure_default_suppliers(db, org.id)

    # Spend
    spend_res = await db.execute(
        select(func.coalesce(func.sum(PurchaseOrder.total_cost), 0.0)).where(PurchaseOrder.organization_id == org.id)
    )
    total_spend = spend_res.scalar() or 0.0

    # Active Orders
    active_res = await db.execute(
        select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.organization_id == org.id,
            PurchaseOrder.status.in_(["ordered", "in_transit", "shipped", "pending_approval"])
        )
    )
    active_orders = active_res.scalar() or 0

    # In-transit shipments
    transit_res = await db.execute(
        select(func.count(ShipmentTracking.id)).where(
            ShipmentTracking.organization_id == org.id,
            ShipmentTracking.current_status.in_(["label_created", "picked_up", "in_transit", "out_for_delivery"])
        )
    )
    in_transit = transit_res.scalar() or 0

    # Connected suppliers
    sup_res = await db.execute(
        select(func.count(Supplier.id)).where(Supplier.organization_id == org.id, Supplier.status == "active")
    )
    suppliers_count = sup_res.scalar() or 0

    # Inventory items & units
    inv_res = await db.execute(
        select(
            func.count(InventoryItem.id),
            func.coalesce(func.sum(InventoryItem.quantity_in_transit), 0)
        ).where(InventoryItem.organization_id == org.id)
    )
    inv_row = inv_res.one()
    inv_count, units_transit = inv_row[0] or 0, inv_row[1] or 0

    # Total Bot Orders
    bot_orders_res = await db.execute(
        select(func.count(PurchaseOrder.id)).where(PurchaseOrder.organization_id == org.id)
    )
    total_bot_orders = bot_orders_res.scalar() or 0

    # Delivered / Complete Success Orders
    delivered_res = await db.execute(
        select(func.count(PurchaseOrder.id)).where(PurchaseOrder.organization_id == org.id, PurchaseOrder.status == "delivered")
    )
    delivered_orders = delivered_res.scalar() or 0

    # Dropship vs Warehouse Counts
    dropship_res = await db.execute(
        select(func.count(PurchaseOrder.id)).where(PurchaseOrder.organization_id == org.id, PurchaseOrder.destination_type == "customer_dropship")
    )
    dropship_orders = dropship_res.scalar() or 0
    warehouse_orders = max(0, total_bot_orders - dropship_orders)

    # Shipping Success Rate: delivered / total bot orders (if 0 orders, default to 100.0)
    if total_bot_orders > 0:
        shipping_success_rate = round((delivered_orders / total_bot_orders) * 100.0, 1)
    else:
        shipping_success_rate = 100.0

    # Sales Revenue linked to fulfilled orders (or total tenant sales)
    linked_sales_res = await db.execute(
        select(func.coalesce(func.sum(ClientSale.amount), 0.0)).join(
            PurchaseOrder, PurchaseOrder.client_sale_id == ClientSale.id
        ).where(PurchaseOrder.organization_id == org.id)
    )
    linked_sales = linked_sales_res.scalar() or 0.0

    if linked_sales == 0.0:
        all_sales_res = await db.execute(
            select(func.coalesce(func.sum(ClientSale.amount), 0.0)).where(
                ClientSale.organization_id == org.id,
                ClientSale.status != "cancelled"
            )
        )
        total_sales_rev = all_sales_res.scalar() or 0.0
    else:
        total_sales_rev = linked_sales

    net_margin = round(total_sales_rev - total_spend, 2) if total_sales_rev > 0 else 0.0
    margin_pct = round(((total_sales_rev - total_spend) / total_sales_rev) * 100.0, 1) if (total_sales_rev > 0 and total_sales_rev > total_spend) else 0.0

    return {
        "total_procurement_spend": round(total_spend, 2),
        "active_orders_count": active_orders,
        "in_transit_shipments_count": in_transit,
        "connected_suppliers_count": suppliers_count,
        "inventory_items_count": inv_count,
        "units_in_transit": units_transit,
        "total_sales_revenue": round(total_sales_rev, 2),
        "net_profit_margin": net_margin,
        "profit_margin_pct": margin_pct,
        "shipping_success_rate": shipping_success_rate,
        "total_bot_orders": total_bot_orders,
        "delivered_orders_count": delivered_orders,
        "dropship_orders_count": dropship_orders,
        "warehouse_orders_count": warehouse_orders
    }
