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

    model_config = ConfigDict(from_attributes=True)
