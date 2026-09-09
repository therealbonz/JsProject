from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field

# Supplier Schemas
class SupplierBase(BaseModel):
    name: str
    code: str
    website_url: str
    adapter_type: str = "web_automation"  # api, web_automation, punchout, custom
    status: str = "active"
    category: str = "General Supply"
    lead_days_estimate: int = 2
    auth_config: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None

class SupplierCreate(SupplierBase):
    pass

class SupplierResponse(SupplierBase):
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Item within a Purchase Order
class PurchaseOrderItem(BaseModel):
    sku: str
    name: str
    qty: int
    unit_cost: float
    total: float
    notes: Optional[str] = None

# Purchase Order Schemas
class PurchaseOrderCreate(BaseModel):
    supplier_id: str
    client_sale_id: Optional[str] = None
    items: List[PurchaseOrderItem]
    destination_type: str = "warehouse"  # warehouse, customer_dropship
    destination_address: Optional[str] = None
    notes: Optional[str] = None

class ShipmentTrackingBrief(BaseModel):
    id: str
    carrier: str
    tracking_number: str
    tracking_url: Optional[str] = None
    current_status: str
    origin: str
    destination: str
    estimated_delivery: Optional[datetime] = None
    actual_delivery: Optional[datetime] = None
    history_events: List[Dict[str, Any]] = Field(default_factory=list)
    model_config = ConfigDict(from_attributes=True)

class PurchaseOrderResponse(BaseModel):
    id: str
    po_number: str
    supplier_id: str
    client_sale_id: Optional[str] = None
    total_cost: float
    currency: str
    status: str
    requires_approval: bool
    approved_by: Optional[str] = None
    approval_reason: Optional[str] = None
    items_json: List[Dict[str, Any]] = Field(default_factory=list)
    confirmation_code: Optional[str] = None
    placed_at: datetime
    ordered_by_agent: bool
    destination_type: str
    destination_address: Optional[str] = None
    notes: Optional[str] = None
    supplier_name: Optional[str] = None
    client_sale_order_number: Optional[str] = None
    client_name: Optional[str] = None
    client_sale_amount: Optional[float] = None
    profit_margin_dollars: Optional[float] = None
    profit_margin_pct: Optional[float] = None
    shipping_success_status: Optional[str] = None
    shipping_stage_pct: Optional[int] = None
    shipments: List[ShipmentTrackingBrief] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# AI Auto-Fill Request
class AutoFillOrderRequest(BaseModel):
    requirement_prompt: str = Field(..., description="E.g. 'Order 50 boxes of corrugated cartons and 20 rolls of packing tape'")
    preferred_supplier_code: Optional[str] = Field(None, description="Optional supplier code like amazon_business, grainger, digikey, or auto")
    destination_type: str = "warehouse"  # warehouse, customer_dropship
    destination_address: Optional[str] = None
    client_sale_id: Optional[str] = None
    max_budget_limit: Optional[float] = 500.0

# Tracking & Dispatch Schemas
class ShipmentAdvanceRequest(BaseModel):
    custom_note: Optional[str] = None
    next_location: Optional[str] = None

class DispatchShipmentRequest(BaseModel):
    purchase_order_id: str
    carrier: str = "UPS"  # UPS, FedEx, USPS, Freight
    destination: str
    client_sale_id: Optional[str] = None
    notes: Optional[str] = None

class ProcurementStatsResponse(BaseModel):
    total_procurement_spend: float
    active_orders_count: int
    in_transit_shipments_count: int
    connected_suppliers_count: int
    inventory_items_count: int
    units_in_transit: int
    total_sales_revenue: Optional[float] = 0.0
    net_profit_margin: Optional[float] = 0.0
    profit_margin_pct: Optional[float] = 0.0
    shipping_success_rate: Optional[float] = 0.0
    total_bot_orders: Optional[int] = 0
    delivered_orders_count: Optional[int] = 0
    dropship_orders_count: Optional[int] = 0
    warehouse_orders_count: Optional[int] = 0
