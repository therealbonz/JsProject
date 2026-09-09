from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, ForeignKey, JSON, desc
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import CommonMixin, TenantMixin, get_utc_now

class Supplier(Base, CommonMixin, TenantMixin):
    __tablename__ = "suppliers"

    name = Column(String(255), nullable=False, index=True)
    code = Column(String(50), nullable=False, index=True)  # amazon_business, grainger, digikey, custom_web
    website_url = Column(String(500), nullable=False)
    adapter_type = Column(String(50), default="web_automation", nullable=False)  # api, web_automation, punchout, custom
    status = Column(String(50), default="active", nullable=False)  # active, simulated, paused, error
    category = Column(String(100), default="General Supply", nullable=False)
    lead_days_estimate = Column(Integer, default=2, nullable=False)
    auth_config = Column(JSON, default=dict, nullable=False)
    notes = Column(Text, nullable=True)

    # Relationships
    purchase_orders = relationship("PurchaseOrder", back_populates="supplier", cascade="all, delete-orphan", order_by=lambda: desc(PurchaseOrder.created_at))

class PurchaseOrder(Base, CommonMixin, TenantMixin):
    __tablename__ = "purchase_orders"

    po_number = Column(String(100), nullable=False, index=True)
    supplier_id = Column(String(36), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    client_sale_id = Column(String(36), ForeignKey("client_sales.id", ondelete="SET NULL"), nullable=True, index=True)

    total_cost = Column(Float, default=0.0, nullable=False)
    currency = Column(String(10), default="USD", nullable=False)
    status = Column(String(50), default="ordered", nullable=False, index=True)
    # pending_approval, auto_approved, ordered, shipped, in_transit, delivered, cancelled

    requires_approval = Column(Boolean, default=False, nullable=False)
    approved_by = Column(String(100), nullable=True)
    approval_reason = Column(Text, nullable=True)

    items_json = Column(JSON, default=list, nullable=False)
    # [{"sku": "...", "name": "...", "qty": 10, "unit_cost": 24.50, "total": 245.00}]

    confirmation_code = Column(String(100), nullable=True)
    placed_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False)
    ordered_by_agent = Column(Boolean, default=True, nullable=False)
    
    destination_type = Column(String(50), default="warehouse", nullable=False)  # warehouse, customer_dropship
    destination_address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    supplier = relationship("Supplier", back_populates="purchase_orders")
    client_sale = relationship("ClientSale", back_populates="purchase_orders")
    shipments = relationship("ShipmentTracking", back_populates="purchase_order", cascade="all, delete-orphan", order_by=lambda: desc(ShipmentTracking.created_at))

class ShipmentTracking(Base, CommonMixin, TenantMixin):
    __tablename__ = "shipment_trackings"

    purchase_order_id = Column(String(36), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    carrier = Column(String(50), default="UPS", nullable=False)  # UPS, FedEx, USPS, DHL, Freight
    tracking_number = Column(String(100), nullable=False, index=True)
    tracking_url = Column(String(500), nullable=True)
    
    current_status = Column(String(50), default="label_created", nullable=False, index=True)
    # label_created, picked_up, in_transit, out_for_delivery, delivered

    origin = Column(String(255), default="Supplier Fulfillment Hub", nullable=False)
    destination = Column(String(255), default="Primary Distribution Warehouse", nullable=False)
    
    estimated_delivery = Column(DateTime(timezone=True), nullable=True)
    actual_delivery = Column(DateTime(timezone=True), nullable=True)
    history_events = Column(JSON, default=list, nullable=False)
    # [{"timestamp": "...", "status": "...", "location": "...", "description": "..."}]

    # Relationships
    purchase_order = relationship("PurchaseOrder", back_populates="shipments")

class InventoryItem(Base, CommonMixin, TenantMixin):
    __tablename__ = "inventory_items"

    sku = Column(String(100), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(100), default="General Supply", nullable=False)
    quantity_on_hand = Column(Integer, default=0, nullable=False)
    quantity_in_transit = Column(Integer, default=0, nullable=False)
    reorder_threshold = Column(Integer, default=10, nullable=False)
    unit_cost = Column(Float, default=0.0, nullable=False)
    location = Column(String(100), default="Main Warehouse - Bay 4", nullable=False)
    preferred_supplier_id = Column(String(36), ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True)
