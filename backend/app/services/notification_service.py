import logging
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.crm import ClientSale, CustomerNotification

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def get_public_tracking_url(order_number: str, base_url: Optional[str] = None) -> str:
        if not base_url:
            base_url = "https://therealbonz.com/JsProject"
        base_url = base_url.rstrip("/")
        return f"{base_url}/track/{order_number}"

    @classmethod
    async def create_and_send_notification(
        cls,
        db: AsyncSession,
        sale: ClientSale,
        event_type: str,
        channel: str = "email",
        custom_title: Optional[str] = None,
        custom_message: Optional[str] = None,
        carrier: Optional[str] = None,
        tracking_number: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> CustomerNotification:
        tracking_url = cls.get_public_tracking_url(sale.order_number, base_url)
        recipient = sale.customer_email or (f"{sale.client.account_name} Purchasing" if sale.client else "customer@example.com")
        if channel == "sms" and sale.customer_phone:
            recipient = sale.customer_phone

        # Standard templates based on event
        titles = {
            "order_confirmed": f"Order Confirmed: {sale.order_number}",
            "payment_received": f"Payment Received for Order {sale.order_number}",
            "dispatched": f"Your Order {sale.order_number} Has Shipped via {carrier or 'Carrier'}",
            "in_transit": f"Delivery Update: Order {sale.order_number} is In Transit",
            "out_for_delivery": f"Out for Delivery: Order {sale.order_number}",
            "delivered": f"Delivered: Order {sale.order_number} has arrived",
        }

        messages = {
            "order_confirmed": (
                f"Thank you for your order #{sale.order_number}. "
                f"Your order of {sale.items_summary} is currently being prepared for autonomous fulfillment. "
                f"Live status: {tracking_url}"
            ),
            "payment_received": (
                f"Payment of ${sale.amount:.2f} received for Order #{sale.order_number}. "
                f"Our AI fulfillment bot has triggered autonomous sourcing and direct dispatch. "
                f"Track live: {tracking_url}"
            ),
            "dispatched": (
                f"Great news! Your order #{sale.order_number} has been dispatched with {carrier or 'Carrier'}. "
                f"Tracking #{tracking_number or 'Assigned'}. "
                f"Follow your package milestones here: {tracking_url}"
            ),
            "in_transit": (
                f"Your package for order #{sale.order_number} is in transit with {carrier or 'Carrier'}. "
                f"Live tracking: {tracking_url}"
            ),
            "out_for_delivery": (
                f"Heads up! Order #{sale.order_number} is out for delivery today. "
                f"Verify live updates: {tracking_url}"
            ),
            "delivered": (
                f"Order #{sale.order_number} has been delivered successfully! "
                f"Thank you for choosing Acme Supply. View proof of delivery: {tracking_url}"
            ),
        }

        title = custom_title or titles.get(event_type, f"Order Notification: {sale.order_number}")
        message_body = custom_message or messages.get(event_type, f"Status update for order #{sale.order_number}. Track live: {tracking_url}")

        notification = CustomerNotification(
            organization_id=sale.organization_id,
            client_sale_id=sale.id,
            recipient=recipient,
            channel=channel,
            event_type=event_type,
            title=title,
            message_body=message_body,
            tracking_url=tracking_url,
            status="sent",
        )
        db.add(notification)
        await db.commit()
        await db.refresh(notification)

        logger.info(f"Dispatched {channel.upper()} [{event_type}] to {recipient}: {title}")
        return notification
