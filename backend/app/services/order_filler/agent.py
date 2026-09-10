import uuid
import re
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.procurement import Supplier, PurchaseOrder, ShipmentTracking, InventoryItem
from app.models.crm import ClientSale
from app.services.order_filler.amazon_adapter import AmazonBusinessAdapter
from app.services.order_filler.grainger_adapter import GraingerAdapter
from app.services.order_filler.digikey_adapter import DigiKeyAdapter
from app.services.order_filler.generic_web_adapter import GenericWebStoreAdapter
from app.services.order_filler.base_adapter import BaseSupplierAdapter
from app.services.gemini_service import gemini_service

logger = logging.getLogger(__name__)

class OrderFillerAgent:
    """
    Central AI Order Filler & Supply Chain Logistics Engine.
    Handles autonomous catalog matching, supplier ordering, tracking management,
    and delivery fulfillment with spend guardrails.
    """
    def __init__(self):
        self.builtin_adapters: Dict[str, BaseSupplierAdapter] = {
            "amazon_business": AmazonBusinessAdapter(),
            "grainger": GraingerAdapter(),
            "digikey": DigiKeyAdapter(),
        }

    def get_adapter_for_supplier(self, supplier: Supplier) -> BaseSupplierAdapter:
        if supplier.code in self.builtin_adapters:
            return self.builtin_adapters[supplier.code]
        return GenericWebStoreAdapter(
            website_url=supplier.website_url,
            supplier_name=supplier.name,
            code=supplier.code
        )

    async def ensure_default_suppliers(self, db: AsyncSession, org_id: str):
        """Seed pre-configured supplier connections if none exist for organization."""
        stmt = select(Supplier).where(Supplier.organization_id == org_id)
        res = await db.execute(stmt)
        existing = res.scalars().all()
        if not existing:
            defaults = [
                Supplier(
                    organization_id=org_id,
                    name="Amazon Business",
                    code="amazon_business",
                    website_url="https://business.amazon.com",
                    adapter_type="api",
                    status="active",
                    category="Packaging & General",
                    lead_days_estimate=2,
                    notes="Enterprise Prime account with 2-day delivery guarantees."
                ),
                Supplier(
                    organization_id=org_id,
                    name="W.W. Grainger Industrial Supply",
                    code="grainger",
                    website_url="https://www.grainger.com",
                    adapter_type="web_automation",
                    status="active",
                    category="Industrial MRO & Safety",
                    lead_days_estimate=1,
                    notes="Branch pickup & next-day commercial delivery available."
                ),
                Supplier(
                    organization_id=org_id,
                    name="DigiKey Electronics",
                    code="digikey",
                    website_url="https://www.digikey.com",
                    adapter_type="api",
                    status="active",
                    category="Electronics & Sensors",
                    lead_days_estimate=2,
                    notes="Direct manufacturer reels, IoT microcontrollers, and DIN rails."
                ),
                Supplier(
                    organization_id=org_id,
                    name="McMaster-Carr Supply Co.",
                    code="mcmaster",
                    website_url="https://www.mcmaster.com",
                    adapter_type="web_automation",
                    status="active",
                    category="Hardware & Raw Materials",
                    lead_days_estimate=1,
                    notes="Same-day freight and CAD-grounded hardware parts."
                ),
            ]
            db.add_all(defaults)
            await db.flush()

    async def auto_fill_order(
        self,
        db: AsyncSession,
        org_id: str,
        prompt: str,
        preferred_supplier_code: Optional[str] = None,
        destination_type: str = "warehouse",
        destination_address: Optional[str] = None,
        client_sale_id: Optional[str] = None,
        max_budget_limit: float = 500.0
    ) -> Dict[str, Any]:
        """
        Interprets order requirements, selects optimal supplier, compares catalog,
        enforces spend guardrails, submits order, and creates tracking record.
        """
        await self.ensure_default_suppliers(db, org_id)

        # 1. Fetch available suppliers
        sup_stmt = select(Supplier).where(Supplier.organization_id == org_id, Supplier.status == "active")
        sup_res = await db.execute(sup_stmt)
        suppliers = sup_res.scalars().all()
        if not suppliers:
            raise ValueError("No active suppliers configured for this tenant.")

        # 2. Select target supplier
        target_supplier = None
        if preferred_supplier_code and preferred_supplier_code != "auto":
            target_supplier = next((s for s in suppliers if s.code == preferred_supplier_code), None)

        if not target_supplier:
            # Intelligent routing based on prompt keywords
            p_lower = prompt.lower()
            if any(w in p_lower for w in ["resistor", "esp32", "relay", "sensor", "board", "circuit", "electronic"]):
                target_supplier = next((s for s in suppliers if s.code == "digikey"), suppliers[0])
            elif any(w in p_lower for w in ["filter", "mro", "pallet truck", "degreaser", "sling", "motor", "tool"]):
                target_supplier = next((s for s in suppliers if s.code == "grainger"), suppliers[0])
            elif any(w in p_lower for w in ["mcmaster", "bolt", "screw", "shaft", "fitting"]):
                target_supplier = next((s for s in suppliers if s.code == "mcmaster"), suppliers[0])
            else:
                target_supplier = next((s for s in suppliers if s.code == "amazon_business"), suppliers[0])

        adapter = self.get_adapter_for_supplier(target_supplier)

        # 3. Match items from catalog
        matched_items = await adapter.search_catalog(prompt, limit=3)
        
        # Extract desired quantity from prompt if present (e.g. "Order 25 boxes...")
        qty_match = re.search(r'\b(\d{1,4})\b', prompt)
        parsed_qty = int(qty_match.group(1)) if qty_match else random.choice([5, 10, 20])
        # Cap initial single item qty to reasonable test size if not specified
        if parsed_qty > 200:
            parsed_qty = 50

        order_items = []
        if matched_items:
            primary_item = matched_items[0]
            unit_price = float(primary_item.get("unit_price", 25.0))
            order_items.append({
                "sku": primary_item.get("sku", f"SKU-{random.randint(100, 999)}"),
                "name": primary_item.get("name", prompt.title()),
                "qty": parsed_qty,
                "unit_cost": unit_price,
                "total": round(unit_price * parsed_qty, 2)
            })
        else:
            default_price = 28.50
            order_items.append({
                "sku": f"GEN-{random.randint(100, 999)}",
                "name": prompt.title(),
                "qty": parsed_qty,
                "unit_cost": default_price,
                "total": round(default_price * parsed_qty, 2)
            })

        total_cost = round(sum(it["total"] for it in order_items), 2)
        po_number = f"PO-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

        # 4. Check Spend Guardrails (Human-in-the-Loop policy)
        requires_approval = total_cost > max_budget_limit
        order_status = "pending_approval" if requires_approval else "ordered"
        approval_reason = f"Total spend of ${total_cost:.2f} exceeds auto-purchase threshold of ${max_budget_limit:.2f}." if requires_approval else None

        # 5. Place order if approved / under budget
        order_result = None
        if not requires_approval:
            dest_str = destination_address or ("Main Fulfillment Warehouse, 100 Logistics Blvd" if destination_type == "warehouse" else "Customer Destination")
            order_result = await adapter.place_order(order_items, shipping_address=dest_str)

        # 6. Save PurchaseOrder in Database
        po = PurchaseOrder(
            organization_id=org_id,
            po_number=po_number,
            supplier_id=target_supplier.id,
            client_sale_id=client_sale_id,
            total_cost=total_cost,
            currency="USD",
            status=order_status,
            requires_approval=requires_approval,
            approval_reason=approval_reason,
            items_json=order_items,
            confirmation_code=order_result.get("order_confirmation") if order_result else None,
            ordered_by_agent=True,
            destination_type=destination_type,
            destination_address=destination_address or ("Customer Drop Ship Facility" if destination_type == "customer_dropship" else "Main Fulfillment Warehouse (Bay 4)"),
            notes=f"AI Auto-Filled from prompt: '{prompt}'" + (" (Customer Drop Ship)" if destination_type == "customer_dropship" else "")
        )
        db.add(po)
        await db.flush()

        # 7. Create ShipmentTracking if order was placed
        shipment = None
        if not requires_approval and order_result:
            carrier = order_result.get("carrier", "UPS")
            tracking_num = order_result.get("initial_tracking_number", f"1Z{random.randint(10000000, 99999999)}")
            now_iso = datetime.now(timezone.utc).isoformat()

            shipment = ShipmentTracking(
                organization_id=org_id,
                purchase_order_id=po.id,
                carrier=carrier,
                tracking_number=tracking_num,
                tracking_url=f"https://www.google.com/search?q={carrier}+tracking+{tracking_num}",
                current_status="label_created",
                origin=f"{target_supplier.name} Fulfillment Center",
                destination=po.destination_address,
                estimated_delivery=datetime.now(timezone.utc) + timedelta(days=order_result.get("estimated_delivery_days", 2)),
                history_events=[
                    {
                        "timestamp": now_iso,
                        "status": "label_created",
                        "location": f"{target_supplier.name} Warehouse",
                        "description": f"Shipping label created. Carrier {carrier} electronic notification received."
                    }
                ]
            )
            db.add(shipment)

            # Record in Inventory Items (quantity_in_transit)
            for it in order_items:
                inv_stmt = select(InventoryItem).where(InventoryItem.organization_id == org_id, InventoryItem.sku == it["sku"])
                inv_res = await db.execute(inv_stmt)
                inv_item = inv_res.scalar_one_or_none()
                if not inv_item:
                    inv_item = InventoryItem(
                        organization_id=org_id,
                        sku=it["sku"],
                        name=it["name"],
                        category=target_supplier.category,
                        quantity_on_hand=0,
                        quantity_in_transit=it["qty"],
                        reorder_threshold=10,
                        unit_cost=it["unit_cost"],
                        location="Main Warehouse - Receiving Bay",
                        preferred_supplier_id=target_supplier.id
                    )
                    db.add(inv_item)
                else:
                    inv_item.quantity_in_transit += it["qty"]

            await db.flush()

        await db.commit()

        return {
            "success": True,
            "purchase_order_id": po.id,
            "po_number": po.po_number,
            "supplier": target_supplier.name,
            "total_cost": total_cost,
            "status": order_status,
            "requires_approval": requires_approval,
            "approval_reason": approval_reason,
            "tracking_number": shipment.tracking_number if shipment else None,
            "carrier": shipment.carrier if shipment else None,
            "items": order_items,
            "logs": order_result.get("log", []) if order_result else [f"PO created in pending approval state (Spend: ${total_cost:.2f} > Limit: ${max_budget_limit:.2f})"]
        }

    async def advance_shipment_milestone(
        self,
        db: AsyncSession,
        tracking_id: str,
        custom_note: Optional[str] = None
    ) -> ShipmentTracking:
        """
        Advances shipment tracking status along standard logistics pipeline:
        label_created -> picked_up -> in_transit -> out_for_delivery -> delivered
        When delivered: updates PO status to 'delivered' and moves inventory to on_hand!
        """
        stmt = select(ShipmentTracking).where(ShipmentTracking.id == tracking_id)
        res = await db.execute(stmt)
        tracking = res.scalar_one_or_none()
        if not tracking:
            raise ValueError("Shipment tracking record not found.")

        flow = ["label_created", "picked_up", "in_transit", "out_for_delivery", "delivered"]
        curr_idx = flow.index(tracking.current_status) if tracking.current_status in flow else 0
        if curr_idx < len(flow) - 1:
            next_status = flow[curr_idx + 1]
        else:
            next_status = "delivered"

        tracking.current_status = next_status
        now_dt = datetime.now(timezone.utc)
        now_iso = now_dt.isoformat()

        locations = {
            "picked_up": f"{tracking.origin} Departure Hub",
            "in_transit": "Regional Sorting & Logistics Center",
            "out_for_delivery": f"{tracking.destination} Local Delivery Terminal",
            "delivered": tracking.destination
        }
        loc = locations.get(next_status, "In Transit")

        desc_map = {
            "picked_up": f"Package received and scanned into {tracking.carrier} network.",
            "in_transit": f"In transit to destination facility. High-speed sorting complete.",
            "out_for_delivery": f"Loaded on vehicle. Out for delivery to destination today.",
            "delivered": f"Delivered and signed for at destination. Dock receiving verified."
        }
        msg = custom_note or desc_map.get(next_status, "Status updated.")

        events = list(tracking.history_events or [])
        events.append({
            "timestamp": now_iso,
            "status": next_status,
            "location": loc,
            "description": msg
        })
        tracking.history_events = events

        # If delivered, update PO and stock
        po_stmt = select(PurchaseOrder).where(PurchaseOrder.id == tracking.purchase_order_id)
        po_res = await db.execute(po_stmt)
        po = po_res.scalar_one_or_none()

        if next_status == "delivered":
            tracking.actual_delivery = now_dt
            if po:
                po.status = "delivered"
                # Move items from in_transit to on_hand
                for it in (po.items_json or []):
                    inv_stmt = select(InventoryItem).where(InventoryItem.organization_id == po.organization_id, InventoryItem.sku == it.get("sku"))
                    inv_res = await db.execute(inv_stmt)
                    inv_item = inv_res.scalar_one_or_none()
                    if inv_item:
                        qty = it.get("qty", 0)
                        inv_item.quantity_in_transit = max(0, inv_item.quantity_in_transit - qty)
                        if po.destination_type == "warehouse":
                            inv_item.quantity_on_hand += qty

                # If linked to a client sale, update sale status
                if po.client_sale_id:
                    sale_stmt = select(ClientSale).where(ClientSale.id == po.client_sale_id)
                    sale_res = await db.execute(sale_stmt)
                    sale = sale_res.scalar_one_or_none()
                    if sale and sale.status != "completed":
                        sale.status = "completed"
        elif po and po.status in ["ordered", "pending_approval"]:
            po.status = "in_transit"

        # Dispatch customer milestone notification if linked to a sale
        if po and po.client_sale_id and next_status in ("in_transit", "out_for_delivery", "delivered"):
            try:
                from app.services.notification_service import NotificationService
                s_stmt = select(ClientSale).where(ClientSale.id == po.client_sale_id)
                s_res = await db.execute(s_stmt)
                linked_sale = s_res.scalar_one_or_none()
                if linked_sale:
                    await NotificationService.create_and_send_notification(
                        db=db,
                        sale=linked_sale,
                        event_type=next_status,
                        carrier=tracking.carrier,
                        tracking_number=tracking.tracking_number
                    )
            except Exception as notify_err:
                logger.warning(f"Milestone notification trigger failed: {notify_err}")

        await db.commit()
        await db.refresh(tracking)
        return tracking

order_filler_agent = OrderFillerAgent()
