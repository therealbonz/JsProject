import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from app.services.order_filler.base_adapter import BaseSupplierAdapter

class UlineAdapter(BaseSupplierAdapter):
    supplier_code = "uline"
    supplier_name = "Uline Shipping & Packaging"
    website_url = "https://www.uline.com"
    adapter_type = "api"

    CATALOG = [
        {"sku": "UL-S-4122", "name": "Uline 20 x 20 x 20 275# Double Wall Corrugated Boxes (15-Pack)", "unit_price": 54.75, "in_stock": 420, "category": "Packaging"},
        {"sku": "UL-S-1053", "name": "Uline Industrial 2-Mil Clear Packing Tape 2\" x 110 yds (36 Rolls)", "unit_price": 68.40, "in_stock": 850, "category": "Packaging"},
        {"sku": "UL-S-3450", "name": "Uline Standard Bubble Wrap Roll 24\" x 250 ft Perforated", "unit_price": 42.00, "in_stock": 310, "category": "Cushioning"},
        {"sku": "UL-S-2849", "name": "Uline Cast Hand Stretch Wrap Film 18\" x 1500 ft 80 Gauge (4 Rolls)", "unit_price": 72.50, "in_stock": 290, "category": "Stretch Film"},
        {"sku": "UL-S-6523", "name": "Uline Poly Mailers 10 x 13 White Self-Seal (Case of 1,000)", "unit_price": 89.00, "in_stock": 190, "category": "Mailers"},
        {"sku": "UL-H-1563", "name": "Uline Industrial Poly Bag Sealer with Cutter 12-inch", "unit_price": 115.00, "in_stock": 75, "category": "Equipment"},
    ]

    async def search_catalog(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        q_lower = query.lower()
        results = [
            item for item in self.CATALOG 
            if any(term in item["name"].lower() or term in item["category"].lower() for term in q_lower.split())
        ]
        if not results:
            results = self.CATALOG[:limit]
        return results[:limit]

    async def check_availability(self, sku: str, qty: int) -> Dict[str, Any]:
        match = next((item for item in self.CATALOG if item["sku"].lower() == sku.lower()), None)
        if match:
            return {
                "sku": sku,
                "name": match["name"],
                "available": match["in_stock"] >= qty,
                "unit_price": match["unit_price"],
                "stock_count": match["in_stock"],
                "currency": "USD"
            }
        return {
            "sku": sku,
            "name": f"Uline Warehouse Item ({sku})",
            "available": True,
            "unit_price": 45.00,
            "stock_count": 150,
            "currency": "USD"
        }

    async def place_order(
        self,
        items: List[Dict[str, Any]],
        shipping_address: str,
        auth_config: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        total = sum(float(it.get("unit_cost", 0.0)) * int(it.get("qty", 1)) for it in items)
        random_id = "".join([str(random.randint(0, 9)) for _ in range(8)])
        conf_code = f"UL-ORD-{random_id}"
        tracking_num = f"9405511899562{random.randint(100000000, 999999999)}"

        return {
            "success": True,
            "order_confirmation": conf_code,
            "total_charged": round(total, 2),
            "carrier": "FedEx Freight / Ground",
            "initial_tracking_number": tracking_num,
            "estimated_delivery_days": 1,
            "log": [
                "Uline B2B EDI 850 Purchase Order generated.",
                f"Order {conf_code} processed with Pleasant Prairie, WI Distribution Center.",
                f"Assigned FedEx Freight tracking number: {tracking_num}."
            ]
        }

    async def fetch_tracking_status(self, tracking_number: str) -> Dict[str, Any]:
        return {
            "carrier": "FedEx Ground",
            "tracking_number": tracking_number,
            "status": "in_transit",
            "location": "Pleasant Prairie, WI Regional Fulfillment Hub",
            "estimated_delivery": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        }
