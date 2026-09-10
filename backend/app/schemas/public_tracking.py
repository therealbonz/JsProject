from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class PublicOrderTrackingResponse(BaseModel):
    order_number: str
    client_name: str
    delivery_address: Optional[str] = None
    items_summary: str
    sale_date: datetime
    payment_status: str  # unpaid, paid, refunded
    carrier: Optional[str] = None
    tracking_number: Optional[str] = None
    tracking_url: Optional[str] = None
    current_status: str  # label_created, picked_up, in_transit, out_for_delivery, delivered, processing, awaiting_payment
    shipping_stage_pct: int  # 0 to 100
    is_delivered: bool = False
    destination_type: Optional[str] = None
    history_events: List[Dict[str, Any]] = []
    stripe_checkout_url: Optional[str] = None
    brand_name: Optional[str] = "Order Bot Distribution"
    brand_logo_url: Optional[str] = None
    brand_accent_color: Optional[str] = "#4f46e5"
    support_email: Optional[str] = "support@therealbonz.com"
    support_phone: Optional[str] = None
    custom_footer_text: Optional[str] = None
    tracking_portal_notice: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
