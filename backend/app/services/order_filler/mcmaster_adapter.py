import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from app.services.order_filler.base_adapter import BaseSupplierAdapter

class McMasterCarrAdapter(BaseSupplierAdapter):
    supplier_code = "mcmaster"
    supplier_name = "McMaster-Carr Supply Company"
    website_url = "https://www.mcmaster.com"
    adapter_type = "api"

    CATALOG = [
        {"sku": "MC-91251A540", "name": "Grade 8 High-Strength Hex Head Screws 3/8\"-16 x 1-1/2\" (Pack of 50)", "unit_price": 22.40, "in_stock": 700, "category": "Fasteners"},
        {"sku": "MC-4524T22", "name": "Multipurpose 6061 Aluminum Rectangular Bar 1/4\" Thick x 2\" Wide x 6 ft", "unit_price": 41.80, "in_stock": 140, "category": "Raw Materials"},
        {"sku": "MC-50785K143", "name": "Extreme-Pressure Hydraulic Hose with Brass Fittings 3/8\" ID x 25 ft", "unit_price": 79.50, "in_stock": 85, "category": "Piping & Tubing"},
        {"sku": "MC-2788K34", "name": "Precision Oil-Resistant Nitrile O-Ring Assortment Kit (382 Pieces)", "unit_price": 38.90, "in_stock": 210, "category": "Sealing"},
        {"sku": "MC-7541A12", "name": "Commercial Heavy-Duty Swivel Caster with Polyurethane Wheel 6\" (500 lb)", "unit_price": 34.25, "in_stock": 160, "category": "Material Handling"},
        {"sku": "MC-8889T44", "name": "Krylon Industrial Rust-Tough Protective Enamel Spray Paint (12-Pack)", "unit_price": 86.40, "in_stock": 95, "category": "Maintenance MRO"},
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
            "name": f"McMaster Industrial Component ({sku})",
            "available": True,
            "unit_price": 49.00,
            "stock_count": 120,
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
        random_id = "".join([str(random.randint(0, 9)) for _ in range(7)])
        conf_code = f"MC-PO-{random_id}"
        tracking_num = f"1Z99999999{random.randint(10000000, 99999999)}"

        return {
            "success": True,
            "order_confirmation": conf_code,
            "total_charged": round(total, 2),
            "carrier": "UPS Next Day Air",
            "initial_tracking_number": tracking_num,
            "estimated_delivery_days": 1,
            "log": [
                "McMaster-Carr Enterprise PunchOut B2B transaction dispatched.",
                f"Order {conf_code} routed to Aurora, OH Mega-Distribution Center.",
                f"Assigned UPS Next Day Air tracking: {tracking_num}."
            ]
        }

    async def fetch_tracking_status(self, tracking_number: str) -> Dict[str, Any]:
        return {
            "carrier": "UPS Next Day Air",
            "tracking_number": tracking_number,
            "status": "in_transit",
            "location": "Aurora, OH Distribution Center",
            "estimated_delivery": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        }
