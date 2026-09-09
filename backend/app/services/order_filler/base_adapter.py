from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseSupplierAdapter(ABC):
    """
    Abstract interface for business supply website integrations.
    Supports API connections, web-automation/punchout, and extensible custom websites.
    """
    supplier_code: str = "generic"
    supplier_name: str = "Generic Business Supplier"
    website_url: str = ""
    adapter_type: str = "web_automation"

    @abstractmethod
    async def search_catalog(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search products, prices, and availability on the supplier's website/API."""
        pass

    @abstractmethod
    async def check_availability(self, sku: str, qty: int) -> Dict[str, Any]:
        """Check live warehouse stock and lead time for given SKU."""
        pass

    @abstractmethod
    async def place_order(
        self,
        items: List[Dict[str, Any]],
        shipping_address: str,
        auth_config: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute purchase order on supplier portal/API.
        Returns: {
            "success": bool,
            "order_confirmation": str,
            "total_charged": float,
            "carrier": str,
            "initial_tracking_number": str,
            "estimated_delivery_days": int,
            "log": List[str]
        }
        """
        pass

    @abstractmethod
    async def fetch_tracking_status(self, tracking_number: str) -> Dict[str, Any]:
        """Fetch live carrier tracking status and milestones."""
        pass
