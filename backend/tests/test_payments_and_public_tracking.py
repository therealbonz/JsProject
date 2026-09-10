import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_payments_and_public_tracking_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register test tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "owner@brandedsolutions.com",
            "password": "Password123!",
            "full_name": "Alicia CEO",
            "organization_name": "Apex Distribution Group"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Create a client account with contact details
        client_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Summit Outdoor Retailers",
            "contact_first_name": "Marcus",
            "contact_last_name": "Vance",
            "contact_email": "marcus@summitoutdoors.example",
            "contact_phone": "+1 (555) 432-8899",
            "company_domain": "summitoutdoors.example",
            "industry": "Outdoor Retail",
            "status": "active"
        }, headers=headers)
        assert client_res.status_code == 200
        client_data = client_res.json()
        client_id = client_data["id"]

        # 3. Log a client sale for dropship
        sale_res = await client.post(f"/api/v1/crm/clients/{client_id}/sales", json={
            "order_number": "SO-88214",
            "amount": 1450.00,
            "items_summary": "10x Industrial Grade Aluminum Hand Trucks",
            "payment_method": "stripe",
            "auto_fulfill_on_payment": True,
            "customer_email": "marcus@summitoutdoors.example",
            "customer_phone": "+1 (555) 432-8899"
        }, headers=headers)
        assert sale_res.status_code == 200
        sale_data = sale_res.json()
        sale_id = sale_data["id"]
        assert sale_data["payment_status"] == "unpaid"
        assert sale_data["auto_fulfill_on_payment"] is True

        # 4. Generate Stripe Checkout session / payment link
        checkout_res = await client.post(f"/api/v1/crm/sales/{sale_id}/create-checkout", json={}, headers=headers)
        assert checkout_res.status_code == 200
        checkout_data = checkout_res.json()
        assert checkout_data["session_id"].startswith("cs_test_")
        assert "/checkout/pay/" in checkout_data["checkout_url"]
        session_id = checkout_data["session_id"]

        # 5. Fetch public hosted checkout details (no auth required)
        public_checkout_res = await client.get(f"/api/v1/public/checkout/{session_id}")
        assert public_checkout_res.status_code == 200
        pub_sess = public_checkout_res.json()
        assert pub_sess["order_number"] == "SO-88214"
        assert pub_sess["amount"] == 1450.00
        assert pub_sess["payment_status"] == "unpaid"
        assert pub_sess["organization_name"] == "Apex Distribution Group"

        # Check hosted checkout HTML page
        html_checkout_res = await client.get(f"/checkout/pay/{session_id}")
        assert html_checkout_res.status_code == 200
        assert "Complete Secure Payment" in html_checkout_res.text
        assert session_id in html_checkout_res.text

        # 6. Simulate payment (or Stripe webhook execution)
        sim_res = await client.post(f"/api/v1/crm/sales/{sale_id}/simulate-payment", headers=headers)
        assert sim_res.status_code == 200
        sim_data = sim_res.json()
        assert sim_data["payment_status"] == "paid"
        assert sim_data["auto_fulfillment_triggered"] is True
        assert sim_data["purchase_order_id"] is not None

        # 7. Check that purchase order was created as dropship to client's address
        orders_res = await client.get("/api/v1/fulfillment/orders", headers=headers)
        assert orders_res.status_code == 200
        all_orders = orders_res.json()
        assert len(all_orders) == 1
        po = all_orders[0]
        assert po["client_sale_order_number"] == "SO-88214"
        assert po["destination_type"] == "customer_dropship"
        assert "Summit Outdoor Retailers" in po["destination_address"]
        assert len(po["shipments"]) == 1
        shipment_id = po["shipments"][0]["id"]
        assert po["shipments"][0]["tracking_number"] is not None

        # 8. Check Public Order Tracking Endpoint (UNAUTHENTICATED)
        track_api_res = await client.get("/api/v1/public/tracking/SO-88214")
        assert track_api_res.status_code == 200
        track_data = track_api_res.json()
        assert track_data["order_number"] == "SO-88214"
        assert track_data["payment_status"] == "paid"
        assert track_data["client_name"] == "Summit Outdoor Retailers"
        assert "Summit Outdoor Retailers" in track_data["delivery_address"]
        assert track_data["current_status"] == "label_created"
        assert track_data["shipping_stage_pct"] == 20
        assert len(track_data["history_events"]) >= 1
        # Ensure sensitive wholesale costs/vendor margins are NOT present
        assert "supplier_name" not in track_data
        assert "profit_margin" not in track_data
        assert "total_cost" not in track_data

        # 9. Verify Public Branded Tracking HTML portal page
        track_html_res = await client.get("/track/SO-88214")
        assert track_html_res.status_code == 200
        assert "Delivery Status" in track_html_res.text
        assert "SO-88214" in track_html_res.text

        # 10. Advance shipment to delivered and verify dispatch notifications
        # Advance: label_created -> picked_up -> in_transit -> out_for_delivery -> delivered
        await client.post(f"/api/v1/fulfillment/shipments/{shipment_id}/advance", headers=headers)
        await client.post(f"/api/v1/fulfillment/shipments/{shipment_id}/advance", headers=headers)
        await client.post(f"/api/v1/fulfillment/shipments/{shipment_id}/advance", headers=headers)
        final_adv = await client.post(f"/api/v1/fulfillment/shipments/{shipment_id}/advance", headers=headers)
        assert final_adv.status_code == 200
        assert final_adv.json()["current_status"] == "delivered"

        # Check tracking updated to delivered
        updated_track = await client.get("/api/v1/public/tracking/SO-88214")
        assert updated_track.json()["current_status"] == "delivered"
        assert updated_track.json()["shipping_stage_pct"] == 100
        assert updated_track.json()["is_delivered"] is True
