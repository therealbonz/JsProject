import uuid
import logging
from typing import Optional, Dict, Any
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.tenant import Organization
from app.models.crm import ClientAccount, ClientSale

logger = logging.getLogger(__name__)

class StripeRecurringService:
    @classmethod
    async def get_or_create_stripe_customer(
        cls,
        db: AsyncSession,
        client: ClientAccount,
        org: Optional[Organization] = None
    ) -> str:
        """
        Retrieves or creates a Stripe Customer record for off-session recurring billing.
        Falls back seamlessly to local simulation if live Stripe keys are not configured.
        """
        if client.stripe_customer_id and client.stripe_customer_id.strip():
            return client.stripe_customer_id

        stripe_key = org.stripe_secret_key if org else None
        is_live = bool(
            stripe_key
            and str(stripe_key).startswith("sk_")
            and not str(stripe_key).startswith("sk_test_")
            and not str(stripe_key).startswith("sk_mock_")
        )

        contact_email = client.primary_contact.email if client.primary_contact else f"client_{client.id[:8]}@example.com"
        account_name = client.account_name

        if is_live:
            try:
                url = "https://api.stripe.com/v1/customers"
                async with httpx.AsyncClient(timeout=10.0) as http_client:
                    res = await http_client.post(
                        url,
                        headers={"Authorization": f"Bearer {stripe_key}"},
                        data={
                            "email": contact_email,
                            "name": account_name,
                            "metadata[client_id]": client.id,
                            "metadata[org_id]": org.id if org else "",
                        }
                    )
                    if res.status_code in (200, 201):
                        data = res.json()
                        cus_id = data.get("id")
                        client.stripe_customer_id = cus_id
                        await db.commit()
                        await db.refresh(client)
                        logger.info(f"[STRIPE LIVE CUSTOMER] Created customer {cus_id} for {account_name}")
                        return cus_id
                    else:
                        logger.warning(f"[STRIPE CUSTOMER ERROR] {res.status_code}: {res.text}")
            except Exception as e:
                logger.error(f"[STRIPE CUSTOMER EXCEPTION] {e}")

        # Simulation fallback
        sim_cus_id = f"cus_sim_{uuid.uuid4().hex[:16]}"
        client.stripe_customer_id = sim_cus_id
        await db.commit()
        await db.refresh(client)
        logger.info(f"[STRIPE SIMULATION] Created simulated customer {sim_cus_id} for {account_name}")
        return sim_cus_id

    @classmethod
    async def attach_payment_method(
        cls,
        db: AsyncSession,
        client: ClientAccount,
        card_brand: str = "visa",
        card_last4: str = "4242",
        payment_method_type: str = "card",
        enable_auto_charge: bool = True,
        auto_charge_limit: Optional[float] = None
    ) -> ClientAccount:
        """
        Stores client payment method metadata and configures auto-charge authorization.
        """
        client.has_payment_method_on_file = True
        client.card_brand = card_brand.lower()
        client.card_last4 = str(card_last4)[-4:]
        client.payment_method_type = payment_method_type
        client.auto_charge_enabled = enable_auto_charge
        client.auto_charge_limit = auto_charge_limit
        await db.commit()
        await db.refresh(client)
        logger.info(f"Attached stored payment method on file for {client.account_name}: {client.card_brand.upper()} ending in {client.card_last4} (auto_charge={client.auto_charge_enabled})")
        return client

    @classmethod
    async def detach_payment_method(
        cls,
        db: AsyncSession,
        client: ClientAccount
    ) -> ClientAccount:
        """
        Removes payment method on file and disables automatic charging.
        """
        client.has_payment_method_on_file = False
        client.auto_charge_enabled = False
        client.card_brand = None
        client.card_last4 = None
        client.auto_charge_limit = None
        await db.commit()
        await db.refresh(client)
        logger.info(f"Removed stored payment method on file for {client.account_name}")
        return client

    @classmethod
    async def toggle_auto_charge(
        cls,
        db: AsyncSession,
        client: ClientAccount,
        enabled: bool,
        limit: Optional[float] = None
    ) -> ClientAccount:
        """
        Updates auto-charge toggle status and safety budget limit.
        """
        client.auto_charge_enabled = enabled
        if limit is not None:
            client.auto_charge_limit = limit
        await db.commit()
        await db.refresh(client)
        logger.info(f"Updated auto-charge for {client.account_name}: enabled={enabled}, limit={limit}")
        return client

    @classmethod
    async def charge_stored_payment_method(
        cls,
        db: AsyncSession,
        client: ClientAccount,
        sale: ClientSale,
        org: Optional[Organization] = None
    ) -> Dict[str, Any]:
        """
        Executes an off-session charge against the client's stored payment method on file.
        Verifies spend limits and updates sale payment status.
        """
        if not client.has_payment_method_on_file:
            return {
                "success": False,
                "error": f"Client '{client.account_name}' does not have a payment method on file."
            }

        # Safety spend limit check
        if client.auto_charge_limit is not None and sale.amount > client.auto_charge_limit:
            return {
                "success": False,
                "error": f"Order total ${sale.amount:.2f} exceeds client's authorized auto-charge limit (${client.auto_charge_limit:.2f})."
            }

        if sale.payment_status == "paid":
            return {
                "success": False,
                "error": f"Order #{sale.order_number} has already been paid."
            }

        stripe_key = org.stripe_secret_key if org else None
        is_live = bool(
            stripe_key
            and str(stripe_key).startswith("sk_")
            and not str(stripe_key).startswith("sk_test_")
            and not str(stripe_key).startswith("sk_mock_")
        )

        customer_id = await cls.get_or_create_stripe_customer(db=db, client=client, org=org)
        amount_cents = int(round(sale.amount * 100))

        if is_live:
            try:
                url = "https://api.stripe.com/v1/payment_intents"
                async with httpx.AsyncClient(timeout=10.0) as http_client:
                    res = await http_client.post(
                        url,
                        headers={"Authorization": f"Bearer {stripe_key}"},
                        data={
                            "customer": customer_id,
                            "amount": str(amount_cents),
                            "currency": "usd",
                            "off_session": "true",
                            "confirm": "true",
                            "description": f"Auto-Replenishment Order #{sale.order_number}",
                            "metadata[client_sale_id]": sale.id,
                            "metadata[order_number]": sale.order_number
                        }
                    )
                    if res.status_code in (200, 201):
                        data = res.json()
                        pi_id = data.get("id")
                        sale.payment_status = "paid"
                        sale.status = "completed"
                        sale.payment_method = f"stored_{client.card_brand or 'card'}"
                        sale.stripe_payment_intent_id = pi_id
                        client.total_revenue = round((client.total_revenue or 0.0) + sale.amount, 2)
                        client.order_count = (client.order_count or 0) + 1
                        await db.commit()
                        await db.refresh(sale)
                        await db.refresh(client)
                        logger.info(f"[STRIPE LIVE OFF-SESSION CHARGE] Successfully charged {customer_id} ${sale.amount:.2f}. PI: {pi_id}")
                        return {
                            "success": True,
                            "mode": "live_stripe",
                            "payment_intent_id": pi_id,
                            "amount": sale.amount,
                            "order_number": sale.order_number
                        }
                    else:
                        logger.warning(f"[STRIPE LIVE CHARGE FAILED] {res.status_code}: {res.text}")
                        return {
                            "success": False,
                            "mode": "live_stripe",
                            "error": res.text
                        }
            except Exception as e:
                logger.error(f"[STRIPE LIVE CHARGE EXCEPTION] {e}")
                return {
                    "success": False,
                    "mode": "live_stripe",
                    "error": str(e)
                }

        # Simulation mode fallback
        sim_pi_id = f"pi_sim_{uuid.uuid4().hex[:18]}"
        sale.payment_status = "paid"
        sale.status = "completed"
        sale.payment_method = f"stored_{client.card_brand or 'card'}"
        sale.stripe_payment_intent_id = sim_pi_id
        client.total_revenue = round((client.total_revenue or 0.0) + sale.amount, 2)
        client.order_count = (client.order_count or 0) + 1
        await db.commit()
        await db.refresh(sale)
        await db.refresh(client)

        logger.info(f"[STRIPE AUTO-CHARGE SIMULATION] Successfully auto-charged {client.account_name} ${sale.amount:.2f} to stored {client.card_brand} ending in {client.card_last4}. PI: {sim_pi_id}")
        return {
            "success": True,
            "mode": "simulated",
            "payment_intent_id": sim_pi_id,
            "amount": sale.amount,
            "card_brand": client.card_brand,
            "card_last4": client.card_last4,
            "order_number": sale.order_number
        }
