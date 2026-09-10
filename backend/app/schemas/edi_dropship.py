from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict

class EDI850ExportResponse(BaseModel):
    po_id: str
    po_number: str
    supplier_code: str
    supplier_name: str
    destination_type: str
    destination_address: Optional[str] = None
    total_cost: float
    currency: str = "USD"
    edi_x12_payload: str
    dropship_json_payload: Dict[str, Any]
    generated_at: datetime

class EDI856ASNWebhookPayload(BaseModel):
    po_number: str
    supplier_code: Optional[str] = None
    carrier: str = "UPS"  # UPS, FedEx, USPS, DHL, Freight
    tracking_number: str
    tracking_url: Optional[str] = None
    shipment_status: str = "in_transit"  # label_created, picked_up, in_transit, out_for_delivery, delivered
    shipped_items: Optional[List[Dict[str, Any]]] = None
    estimated_delivery: Optional[str] = None
    origin: Optional[str] = None
    current_location: Optional[str] = None
    status_event_description: Optional[str] = None

class EDISimulateASNRequest(BaseModel):
    po_id: str
    carrier: Optional[str] = "UPS"
    tracking_number: Optional[str] = None
    shipment_status: Optional[str] = "in_transit"
    current_location: Optional[str] = "Louisville Distribution Hub, KY"
    status_event_description: Optional[str] = "Departed regional sorting facility in transit to recipient"

class EDIWebhookReceipt(BaseModel):
    success: bool
    message: str
    po_number: str
    tracking_number: str
    carrier: str
    shipment_status: str
    updated_sale_id: Optional[str] = None
    notification_sent: bool = False
    timestamp: datetime
