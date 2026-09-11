import re
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.models.procurement import Supplier, PurchaseOrder, ShipmentTracking
from app.models.crm import ClientSale, ClientAccount
from app.models.tenant import Organization, User
from app.services.audit_service import audit_service
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

class EDIService:
    """
    Electronic Data Interchange (EDI) & Dropship Webhook Engine.
    Handles ANSI ASC X12 EDI 850 Purchase Order compilation, JSON dropship exports,
    and EDI 856 Advance Ship Notice (ASN) webhook ingestion with real-time parcel tracking.
    """

    @staticmethod
    def generate_edi_850(
        po: PurchaseOrder,
        supplier: Supplier,
        organization: Organization
    ) -> Dict[str, Any]:
        """
        Generates standard ANSI ASC X12 EDI 850 purchase order transaction text
        and modern REST dropship JSON payload.
        """
        now = datetime.now(timezone.utc)
        yymmdd = now.strftime("%y%m%d")
        yyyymmdd = now.strftime("%Y%m%d")
        hhmm = now.strftime("%H%M")
        ctrl_num = f"{abs(hash(po.id)) % 1000000000:09d}"
        grp_ctrl = f"{abs(hash(po.po_number)) % 1000000:06d}"
        
        sender_id = organization.slug.upper()[:15].ljust(15)
        receiver_id = supplier.code.upper()[:15].ljust(15)

        dest_name = "Customer Destination" if po.destination_type == "customer_dropship" else "Main Warehouse"
        dest_addr = po.destination_address or "100 Logistics Blvd, Distribution Bay 4"

        # Build X12 Segments
        segments = []
        segments.append(f"ISA*00*          *00*          *ZZ*{sender_id}*01*{receiver_id}*{yymmdd}*{hhmm}*U*00401*{ctrl_num}*0*P*>~")
        segments.append(f"GS*PO*{organization.slug.upper()}*{supplier.code.upper()}*{yyyymmdd}*{hhmm}*{grp_ctrl}*X*004010~")
        segments.append("ST*850*0001~")
        segments.append(f"BEG*00*SA*{po.po_number}**{yyyymmdd}~")
        segments.append(f"CUR*SE*{po.currency}~")
        segments.append(f"REF*TN*{organization.id[:12]}~")
        if po.client_sale_id:
            segments.append(f"REF*SO*{po.client_sale_id[:12]}~")
        segments.append(f"N1*ST*{dest_name}*92*{dest_addr[:30]}~")
        segments.append(f"N1*BT*{organization.name[:30]}*92*{organization.id[:12]}~")

        items = po.items_json or []
        total_qty = 0
        for idx, item in enumerate(items, 1):
            qty = int(item.get("qty", 1))
            total_qty += qty
            unit_cost = float(item.get("unit_cost", 0.0))
            sku = item.get("sku", f"SKU-{idx}")
            name = item.get("name", "Item")[:25]
            segments.append(f"PO1*{idx}*{qty}*EA*{unit_cost:.2f}*PE*VP*{sku}*IN*{name}~")

        line_count = len(items)
        segments.append(f"CTT*{line_count}*{total_qty}~")
        
        # Segment count includes ST and SE
        st_index = next(i for i, s in enumerate(segments) if s.startswith("ST*850"))
        # Number of segments from ST to SE inclusive
        seg_count = (len(segments) - st_index) + 1
        segments.append(f"SE*{seg_count}*0001~")
        segments.append(f"GE*1*{grp_ctrl}~")
        segments.append(f"IEA*1*{ctrl_num}~")

        x12_text = "\n".join(segments)

        # Build JSON Dropship payload for REST API suppliers
        dropship_json = {
            "edi_document": "850",
            "standard": "ANSI-ASC-X12-004010",
            "po_number": po.po_number,
            "created_at": po.placed_at.isoformat() if po.placed_at else now.isoformat(),
            "vendor": {
                "supplier_id": supplier.id,
                "name": supplier.name,
                "code": supplier.code,
                "website": supplier.website_url,
                "category": supplier.category
            },
            "purchaser": {
                "organization_id": organization.id,
                "organization_name": organization.name,
                "organization_slug": organization.slug
            },
            "shipping": {
                "destination_type": po.destination_type,
                "destination_address": dest_addr,
                "requested_carrier": "STANDARD_GROUND"
            },
            "financials": {
                "total_cost": po.total_cost,
                "currency": po.currency,
                "items_count": line_count,
                "total_quantity": total_qty
            },
            "line_items": [
                {
                    "line_number": idx,
                    "sku": it.get("sku"),
                    "name": it.get("name"),
                    "quantity": it.get("qty"),
                    "unit_cost": it.get("unit_cost"),
                    "total": it.get("total")
                }
                for idx, it in enumerate(items, 1)
            ],
            "linked_client_sale_id": po.client_sale_id
        }

        return {
            "po_id": po.id,
            "po_number": po.po_number,
            "supplier_code": supplier.code,
            "supplier_name": supplier.name,
            "destination_type": po.destination_type,
            "destination_address": po.destination_address,
            "total_cost": po.total_cost,
            "currency": po.currency,
            "edi_x12_payload": x12_text,
            "dropship_json_payload": dropship_json,
            "generated_at": now
        }

    @staticmethod
    async def process_edi_856_asn(
        db: AsyncSession,
        org_id: str,
        payload: Dict[str, Any],
        actor_email: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ingests an EDI 856 Advance Ship Notice (ASN) webhook from a supplier / dropshipper.
        Updates PurchaseOrder, creates/appends ShipmentTracking, updates linked ClientSale,
        and triggers multi-channel customer notifications.
        """
        po_num = payload.get("po_number", "").strip()
        if not po_num:
            raise ValueError("po_number is required in EDI 856 ASN payload.")

        # Find PurchaseOrder
        stmt = select(PurchaseOrder).options(
            selectinload(PurchaseOrder.supplier),
            selectinload(PurchaseOrder.shipments),
            selectinload(PurchaseOrder.client_sale).selectinload(ClientSale.client)
        ).where(
            PurchaseOrder.organization_id == org_id,
            (PurchaseOrder.po_number == po_num) | (PurchaseOrder.confirmation_code == po_num) | (PurchaseOrder.id == po_num)
        )
        res = await db.execute(stmt)
        po = res.scalar_one_or_none()
        if not po:
            raise ValueError(f"Purchase order '{po_num}' not found for this tenant organization.")

        carrier = (payload.get("carrier") or "UPS").upper()
        tracking_num = payload.get("tracking_number") or f"1Z{uuid.uuid4().hex[:12].upper()}"
        tracking_url = payload.get("tracking_url") or f"https://www.google.com/search?q={carrier}+{tracking_num}"
        shipment_status = payload.get("shipment_status", "in_transit").lower()
        location = payload.get("current_location") or "Supplier Fulfillment Gateway"
        desc_event = payload.get("status_event_description") or f"Advance Ship Notice: Package status updated to {shipment_status.replace('_', ' ')}."

        now = datetime.now(timezone.utc)

        # 1. Update PurchaseOrder status
        if shipment_status == "delivered":
            po.status = "delivered"
        elif shipment_status in ["in_transit", "picked_up", "out_for_delivery", "shipped"]:
            po.status = "in_transit"
        elif shipment_status == "label_created":
            po.status = "ordered"

        # 2. Update or Create ShipmentTracking
        shipment = None
        if po.shipments:
            shipment = po.shipments[0]
            shipment.carrier = carrier
            shipment.tracking_number = tracking_num
            shipment.tracking_url = tracking_url
            shipment.current_status = shipment_status

            events = list(shipment.history_events or [])
            events.append({
                "timestamp": now.isoformat(),
                "status": shipment_status,
                "location": location,
                "description": desc_event
            })
            shipment.history_events = events
            if shipment_status == "delivered" and not shipment.actual_delivery:
                shipment.actual_delivery = now
        else:
            shipment = ShipmentTracking(
                organization_id=org_id,
                purchase_order_id=po.id,
                carrier=carrier,
                tracking_number=tracking_num,
                tracking_url=tracking_url,
                current_status=shipment_status,
                origin=payload.get("origin") or (po.supplier.name if po.supplier else "Supplier Hub"),
                destination=po.destination_address or "Primary Distribution Warehouse",
                estimated_delivery=now + timedelta(days=2),
                actual_delivery=now if shipment_status == "delivered" else None,
                history_events=[
                    {
                        "timestamp": now.isoformat(),
                        "status": shipment_status,
                        "location": location,
                        "description": desc_event
                    }
                ]
            )
            db.add(shipment)

        notification_sent = False
        client_sale_id = None

        # 3. Synchronize linked ClientSale and dispatch customer notification
        if po.client_sale:
            sale = po.client_sale
            client_sale_id = sale.id
            
            if shipment_status == "delivered":
                sale.status = "delivered"
                event_type = "delivered"
            elif shipment_status in ["in_transit", "picked_up"]:
                event_type = "in_transit"
            elif shipment_status == "out_for_delivery":
                event_type = "out_for_delivery"
            else:
                event_type = "dispatched"

            try:
                await NotificationService.create_and_send_notification(
                    db=db,
                    sale=sale,
                    event_type=event_type,
                    channel="email",
                    carrier=carrier,
                    tracking_number=tracking_num
                )
                notification_sent = True
            except Exception as notif_err:
                logger.warning(f"Failed to send customer notification for ASN: {notif_err}")

        # 4. Record Immutable Audit Trail
        await audit_service.log_event(
            db=db,
            org_id=org_id,
            action="edi.856_asn_received",
            actor_type="supplier_webhook",
            actor_email=actor_email or "edi-gateway@dropship.system",
            actor_role="supplier_edi",
            target_entity="purchase_order",
            target_id=po.id,
            status="success",
            ip_address=ip_address or "127.0.0.1",
            payload={
                "po_number": po.po_number,
                "carrier": carrier,
                "tracking_number": tracking_num,
                "shipment_status": shipment_status,
                "location": location,
                "client_sale_id": client_sale_id,
                "notification_sent": notification_sent
            }
        )

        await db.commit()
        await db.refresh(po)

        # 5. Dispatch Outbound Developer Webhooks
        try:
            from app.services.webhook_service import WebhookService
            shipment_payload = {
                "po_number": po.po_number,
                "order_number": po.client_sale.order_number if po.client_sale else None,
                "carrier": carrier,
                "tracking_number": tracking_num,
                "tracking_url": tracking_url,
                "shipment_status": shipment_status,
                "location": location,
                "timestamp": now.isoformat()
            }
            await WebhookService.dispatch_event(
                db=db,
                org_id=org_id,
                event_name="shipment.updated",
                payload=shipment_payload
            )
            if shipment_status == "delivered":
                await WebhookService.dispatch_event(
                    db=db,
                    org_id=org_id,
                    event_name="shipment.delivered",
                    payload=shipment_payload
                )
        except Exception as wh_err:
            logger.warning(f"Failed to dispatch outbound shipment webhook: {wh_err}")

        return {
            "success": True,
            "message": f"EDI 856 ASN successfully processed for PO #{po.po_number}. Tracking updated to {carrier} {tracking_num}.",
            "po_number": po.po_number,
            "tracking_number": tracking_num,
            "carrier": carrier,
            "shipment_status": shipment_status,
            "updated_sale_id": client_sale_id,
            "notification_sent": notification_sent,
            "timestamp": now
        }

edi_service = EDIService()
