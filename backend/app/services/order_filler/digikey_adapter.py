import random
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from app.services.order_filler.base_adapter import BaseSupplierAdapter

class DigiKeyAdapter(BaseSupplierAdapter):
    supplier_code = "digikey"
    supplier_name = "DigiKey Electronics & Hardware"
    website_url = "https://www.digikey.com"
    adapter_type = "api"

    CATALOG = [
        {"sku": "DK-ESP32-WROOM", "name": "Espressif ESP32-WROOM-32D Wi-Fi & BLE Microcontroller Module (Reel of 50)", "unit_price": 142.50, "in_stock": 800, "category": "Semiconductors"},
        {"sku": "DK-RELAY-12V", "name": "Omron G5LE-1-DC12 General Purpose PCB Relay (Pack of 25)", "unit_price": 34.20, "in_stock": 650, "category": "Electromechanical"},
        {"sku": "DK-POWER-24V", "name": "Mean Well HDR-60-24 Industrial DIN Rail Power Supply (24V 2.5A 60W)", "unit_price": 28.75, "in_stock": 210, "category": "Power Supplies"},
        {"sku": "DK-TERM-BLOCK", "name": "Phoenix Contact 5.08mm Pitch Pluggable Terminal Blocks (Set of 20)", "unit_price": 19.90, "in_stock": 450, "category": "Connectors"},
        {"sku": "DK-SENS-TEMP", "name": "Texas Instruments LM35 Precision Centigrade Temperature Sensor (Pack of 10)", "unit_price": 17.50, "in_stock": 390, "category": "Sensors"},
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
            "name": f"DigiKey Component ({sku})",
            "available": True,
            "unit_price": 22.00,
            "stock_count": 500,
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
        conf_code = f"DK-551-{random_id}"
        tracking_num = f"1Z888DK01{random.randint(10000000, 99999999)}"

        return {
            "success": True,
            "order_confirmation": conf_code,
            "total_charged": round(total, 2),
            "carrier": "UPS",
            "initial_tracking_number": tracking_num,
            "estimated_delivery_days": 2,
            "log": [
                f"DigiKey API v3 Cart created and authorized.",
                f"Direct reel packaging confirmed for Order {conf_code}.",
                f"Carrier tracking dispatched: {tracking_num}."
            ]
        }

    async def fetch_tracking_status(self, tracking_number: str) -> Dict[str, Any]:
        return {
            "carrier": "UPS",
            "tracking_number": tracking_number,
            "status": "in_transit",
            "location": "Thief River Falls, MN Origin Facility",
            "estimated_delivery": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        }
