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
async def test_order_fulfillment_end_to_end():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register test tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "procurement@acme.com",
            "password": "Password123!",
            "full_name": "Dave Procurement",
            "organization_name": "Acme Logistics Global"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Verify default suppliers are seeded
        sup_res = await client.get("/api/v1/fulfillment/suppliers", headers=headers)
        assert sup_res.status_code == 200
        suppliers = sup_res.json()
        assert len(suppliers) >= 4
        sup_codes = [s["code"] for s in suppliers]
        assert "amazon_business" in sup_codes
        assert "grainger" in sup_codes
        assert "digikey" in sup_codes
        assert "mcmaster" in sup_codes

        # 3. Add custom business supply website connector
        add_sup_res = await client.post("/api/v1/fulfillment/suppliers", json={
            "name": "Fastenal Industrial Supply",
            "code": "fastenal",
            "website_url": "https://www.fastenal.com",
            "adapter_type": "web_automation",
            "category": "Fasteners & OEM",
            "lead_days_estimate": 2,
            "notes": "Contract pricing enabled"
        }, headers=headers)
        assert add_sup_res.status_code == 200
        assert add_sup_res.json()["name"] == "Fastenal Industrial Supply"

        # 4. AI Order Filler: Execute order under spend limit (auto-approved)
        autofill_res = await client.post("/api/v1/fulfillment/autofill", json={
            "requirement_prompt": "Order 5 boxes of heavy-duty corrugated cartons from Amazon Business",
            "preferred_supplier_code": "amazon_business",
            "destination_address": "Main Warehouse Bay 4, 100 Supply Chain Blvd",
            "max_budget_limit": 500.0
        }, headers=headers)
        assert autofill_res.status_code == 200
        order_data = autofill_res.json()
        assert order_data["success"] is True
        assert order_data["status"] == "ordered"
        assert order_data["requires_approval"] is False
        assert order_data["tracking_number"] is not None
        assert order_data["carrier"] == "UPS"
        po_id_1 = order_data["purchase_order_id"]

        # 5. Verify PO and Shipment tracking were created in database
        po_res = await client.get("/api/v1/fulfillment/orders", headers=headers)
        assert po_res.status_code == 200
        orders = po_res.json()
        assert len(orders) == 1
        po1 = orders[0]
        assert po1["id"] == po_id_1
        assert len(po1["shipments"]) == 1
        tracking_id_1 = po1["shipments"][0]["id"]
        assert po1["shipments"][0]["current_status"] == "label_created"

        # 6. Advance shipment tracking milestone
        advance_res = await client.post(f"/api/v1/fulfillment/shipments/{tracking_id_1}/advance", headers=headers)
        assert advance_res.status_code == 200
        assert advance_res.json()["current_status"] == "picked_up"

        # Advance milestone through in_transit, out_for_delivery, delivered
        await client.post(f"/api/v1/fulfillment/shipments/{tracking_id_1}/advance", headers=headers) # in_transit
        await client.post(f"/api/v1/fulfillment/shipments/{tracking_id_1}/advance", headers=headers) # out_for_delivery
        deliv_res = await client.post(f"/api/v1/fulfillment/shipments/{tracking_id_1}/advance", headers=headers) # delivered
        assert deliv_res.json()["current_status"] == "delivered"

        # Check PO status is now delivered
        po_check = await client.get("/api/v1/fulfillment/orders", headers=headers)
        assert po_check.json()[0]["status"] == "delivered"

        # 7. AI Order Filler: Execute order EXCEEDING spend limit (guardrail halt)
        high_spend_res = await client.post("/api/v1/fulfillment/autofill", json={
            "requirement_prompt": "Order 150 units of hydraulic pallet trucks from Grainger",
            "preferred_supplier_code": "grainger",
            "destination_address": "Main Warehouse Bay 4",
            "max_budget_limit": 500.0  # Limit is $500, pallet trucks are $495 each so 150 units is ~$74,250
        }, headers=headers)
        assert high_spend_res.status_code == 200
        high_order = high_spend_res.json()
        assert high_order["requires_approval"] is True
        assert high_order["status"] == "pending_approval"
        assert "exceeds auto-purchase threshold" in high_order["approval_reason"]
        po_id_2 = high_order["purchase_order_id"]

        # 8. Human-in-the-Loop Manager Approval
        approve_res = await client.post(f"/api/v1/fulfillment/orders/{po_id_2}/approve", headers=headers)
        assert approve_res.status_code == 200
        assert approve_res.json()["success"] is True
        assert approve_res.json()["tracking_number"] is not None

        # Verify PO 2 is now executed
        po_check2 = await client.get("/api/v1/fulfillment/orders", headers=headers)
        po2 = next(o for o in po_check2.json() if o["id"] == po_id_2)
        assert po2["status"] == "ordered"
        assert len(po2["shipments"]) == 1

        # 9. Outbound Dispatch: Ship inventory to customer/destination
        dispatch_res = await client.post("/api/v1/fulfillment/shipments/dispatch", json={
            "purchase_order_id": po_id_1,
            "carrier": "FedEx",
            "destination": "Apex Manufacturing Solutions, 400 Industrial Parkway, Chicago, IL"
        }, headers=headers)
        assert dispatch_res.status_code == 200
        assert dispatch_res.json()["success"] is True
        assert "dispatched" in dispatch_res.json()["message"]
        assert dispatch_res.json()["carrier"] == "FEDEX"

        # 10. Check Procurement Overview Stats
        stats_res = await client.get("/api/v1/fulfillment/stats", headers=headers)
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert stats["total_procurement_spend"] > 0
        assert stats["connected_suppliers_count"] >= 5  # 4 defaults + 1 custom added


@pytest.mark.asyncio
async def test_order_bot_sales_tracking_dropship_success_metrics():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "bot_ops@apex.com",
            "password": "Password123!",
            "full_name": "Alex Ops",
            "organization_name": "Apex Fulfillment Logistics"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # Create Client Account
        client_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Omni Distribution Partners",
            "contact_first_name": "Michael",
            "contact_last_name": "Scott",
            "contact_email": "mscott@omni.com",
            "account_tier": "enterprise"
        }, headers=headers)
        assert client_res.status_code == 200
        client_id = client_res.json()["id"]

        # Log a Client Sale ($2,500.00)
        sale_res = await client.post(f"/api/v1/crm/clients/{client_id}/sales", json={
            "amount": 2500.00,
            "order_number": "ORD-OMNI-9001",
            "items_summary": "10x Industrial Corrugated Cartons, 2x Packaging Tape Rolls",
            "payment_method": "credit_terms_30",
            "sales_rep_name": "Dwight Schrute"
        }, headers=headers)
        assert sale_res.status_code == 200
        sale_data = sale_res.json()
        sale_id = sale_data["id"]

        # AI Order Bot: Auto-fill order linked to Client Sale with Direct Customer Dropship
        autofill_res = await client.post("/api/v1/fulfillment/autofill", json={
            "requirement_prompt": "Order 10 boxes of heavy-duty corrugated cartons and 2 rolls of tape from Amazon Business",
            "preferred_supplier_code": "amazon_business",
            "destination_type": "customer_dropship",
            "destination_address": "Omni Logistics Hub, Bay 9, 100 Enterprise Way, Scranton, PA",
            "client_sale_id": sale_id,
            "max_budget_limit": 1000.0
        }, headers=headers)
        assert autofill_res.status_code == 200
        po_data = autofill_res.json()
        assert po_data["success"] is True
        po_id = po_data["purchase_order_id"]

        # Verify PO was enriched with sales, tracking, margin, and drop ship fields
        orders_res = await client.get("/api/v1/fulfillment/orders", headers=headers)
        assert orders_res.status_code == 200
        orders = orders_res.json()
        assert len(orders) == 1
        po = orders[0]
        assert po["id"] == po_id
        assert po["destination_type"] == "customer_dropship"
        assert "Omni Logistics Hub" in po["destination_address"]
        assert po["client_sale_id"] == sale_id
        assert po["client_sale_order_number"] == "ORD-OMNI-9001"
        assert po["client_name"] == "Omni Distribution Partners"
        assert po["client_sale_amount"] == 2500.00
        assert po["profit_margin_dollars"] > 0
        assert po["profit_margin_pct"] > 0
        assert po["shipping_success_status"] == "Label Created / Dispatched"
        assert po["shipping_stage_pct"] == 25
        assert len(po["shipments"]) == 1

        tracking_id = po["shipments"][0]["id"]
        assert po["shipments"][0]["tracking_number"] is not None

        # Advance carrier tracking to full delivery (100% complete success)
        await client.post(f"/api/v1/fulfillment/shipments/{tracking_id}/advance", headers=headers) # picked_up
        await client.post(f"/api/v1/fulfillment/shipments/{tracking_id}/advance", headers=headers) # in_transit
        await client.post(f"/api/v1/fulfillment/shipments/{tracking_id}/advance", headers=headers) # out_for_delivery
        deliv_res = await client.post(f"/api/v1/fulfillment/shipments/{tracking_id}/advance", headers=headers) # delivered
        assert deliv_res.json()["current_status"] == "delivered"

        # Verify delivered PO has 100% Complete Success
        orders_deliv = await client.get("/api/v1/fulfillment/orders", headers=headers)
        po_deliv = orders_deliv.json()[0]
        assert po_deliv["status"] == "delivered"
        assert po_deliv["shipping_success_status"] == "Complete Success (Delivered)"
        assert po_deliv["shipping_stage_pct"] == 100

        # Verify stats endpoint reports complete order bot success metrics
        stats_res = await client.get("/api/v1/fulfillment/stats", headers=headers)
        assert stats_res.status_code == 200
        stats = stats_res.json()
        assert stats["total_sales_revenue"] == 2500.00
        assert stats["total_procurement_spend"] == po["total_cost"]
        assert stats["net_profit_margin"] == round(2500.00 - po["total_cost"], 2)
        assert stats["profit_margin_pct"] > 0
        assert stats["shipping_success_rate"] == 100.0
        assert stats["total_bot_orders"] == 1
        assert stats["delivered_orders_count"] == 1
        assert stats["dropship_orders_count"] == 1
        assert stats["warehouse_orders_count"] == 0

        # Verify Client Sales endpoints return linked PO and tracking details
        sales_res = await client.get(f"/api/v1/crm/clients/{client_id}/sales", headers=headers)
        assert sales_res.status_code == 200
        client_sales = sales_res.json()
        assert len(client_sales) == 1
        assert client_sales[0]["po_number"] == po["po_number"]
        assert client_sales[0]["tracking_number"] == po["shipments"][0]["tracking_number"]
        assert client_sales[0]["carrier"] == po["shipments"][0]["carrier"]
        assert client_sales[0]["destination_type"] == "customer_dropship"
        assert client_sales[0]["shipping_status"] == "delivered"

        all_sales_res = await client.get("/api/v1/crm/sales", headers=headers)
        assert all_sales_res.status_code == 200
        assert len(all_sales_res.json()) >= 1

