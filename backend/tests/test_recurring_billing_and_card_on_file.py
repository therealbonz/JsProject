import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.crm import ClientAccount, ClientSale

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_card_on_file_attach_toggle_detach():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register test tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "finance@metropolislogistics.example",
            "password": "SecurePassword123!",
            "full_name": "Helena Vance",
            "organization_name": "Metropolis Logistics Corp"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Create client account
        client_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Pacific Cold Storage Co",
            "contact_first_name": "David",
            "contact_last_name": "Kim",
            "contact_email": "david@pacificcold.example",
            "contact_phone": "+1 (555) 334-9988",
            "company_domain": "pacificcold.example",
            "industry": "Cold Chain Logistics",
            "reorder_cadence_days": 14,
            "status": "active"
        }, headers=headers)
        assert client_res.status_code == 200
        client_data = client_res.json()
        client_id = client_data["id"]
        assert client_data["has_payment_method_on_file"] is False

        # 3. Attach stored corporate card on file
        attach_res = await client.post(f"/api/v1/crm/clients/{client_id}/payment-method/attach", json={
            "card_brand": "visa",
            "card_last4": "4242",
            "payment_method_type": "card",
            "enable_auto_charge": True,
            "auto_charge_limit": 5000.0
        }, headers=headers)
        assert attach_res.status_code == 200
        attached_data = attach_res.json()
        assert attached_data["has_payment_method_on_file"] is True
        assert attached_data["card_brand"] == "visa"
        assert attached_data["card_last4"] == "4242"
        assert attached_data["auto_charge_enabled"] is True
        assert attached_data["auto_charge_limit"] == 5000.0

        # 4. Toggle auto-charge status & update limit
        toggle_res = await client.post(f"/api/v1/crm/clients/{client_id}/payment-method/auto-charge", json={
            "enabled": False,
            "limit": 3000.0
        }, headers=headers)
        assert toggle_res.status_code == 200
        toggled_data = toggle_res.json()
        assert toggled_data["auto_charge_enabled"] is False
        assert toggled_data["auto_charge_limit"] == 3000.0

        # 5. Detach payment method
        detach_res = await client.delete(f"/api/v1/crm/clients/{client_id}/payment-method", headers=headers)
        assert detach_res.status_code == 200
        detached_data = detach_res.json()
        assert detached_data["has_payment_method_on_file"] is False
        assert detached_data["auto_charge_enabled"] is False
        assert detached_data["card_last4"] is None

@pytest.mark.asyncio
async def test_charge_client_sale_with_stored_card():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register test tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "billing@apexindustrial.example",
            "password": "SecurePassword123!",
            "full_name": "Alexander Hayes",
            "organization_name": "Apex Industrial Group"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Create client account
        client_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Summit Robotics Labs",
            "contact_first_name": "Elena",
            "contact_last_name": "Rostova",
            "contact_email": "elena@summitrobotics.example",
            "reorder_cadence_days": 30,
            "status": "active"
        }, headers=headers)
        client_id = client_res.json()["id"]

        # 3. Attach stored card
        await client.post(f"/api/v1/crm/clients/{client_id}/payment-method/attach", json={
            "card_brand": "mastercard",
            "card_last4": "8899",
            "payment_method_type": "card",
            "enable_auto_charge": True,
            "auto_charge_limit": 10000.0
        }, headers=headers)

        # 4. Log a new sales order (unpaid)
        sale_res = await client.post(f"/api/v1/crm/clients/{client_id}/sales", json={
            "amount": 3200.00,
            "status": "invoiced",
            "items_summary": "4x High-Precision Linear Actuators & Power Inverters",
            "auto_fulfill_on_payment": True
        }, headers=headers)
        assert sale_res.status_code == 200
        sale_data = sale_res.json()
        sale_id = sale_data["id"]
        assert sale_data["payment_status"] == "unpaid"

        # 5. Charge sale using stored card on file
        charge_res = await client.post(f"/api/v1/crm/clients/{client_id}/charge-sale/{sale_id}", headers=headers)
        assert charge_res.status_code == 200
        charge_data = charge_res.json()
        assert charge_data["success"] is True
        assert charge_data["payment_status"] == "paid"
        assert charge_data["auto_fulfilled"] is True
        assert charge_data["fulfillment"] is not None
        assert "po_number" in charge_data["fulfillment"]

        # 6. Verify client total_revenue was updated
        async with AsyncSessionLocal() as db:
            c = await db.get(ClientAccount, client_id)
            assert c.total_revenue >= 3200.00

        # 7. Attempting to charge again returns error
        recharge_res = await client.post(f"/api/v1/crm/clients/{client_id}/charge-sale/{sale_id}", headers=headers)
        assert recharge_res.status_code == 400
        assert "already been paid" in recharge_res.json()["detail"]

@pytest.mark.asyncio
async def test_recurring_replenishment_auto_charge_and_safety_limits():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register test tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "ops@aerofleet.example",
            "password": "SecurePassword123!",
            "full_name": "Captain Miller",
            "organization_name": "AeroFleet Components"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Create client account with 21-day cadence
        client_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Skyline Avionics Maintenance",
            "contact_first_name": "Rachel",
            "contact_last_name": "Cross",
            "contact_email": "rachel@skylineavionics.example",
            "reorder_cadence_days": 21,
            "status": "active"
        }, headers=headers)
        client_id = client_res.json()["id"]

        # 3. Attach stored card with a tight $1,000.00 safety limit
        await client.post(f"/api/v1/crm/clients/{client_id}/payment-method/attach", json={
            "card_brand": "amex",
            "card_last4": "1004",
            "payment_method_type": "card",
            "enable_auto_charge": True,
            "auto_charge_limit": 1000.00
        }, headers=headers)

        # 4. Trigger replenishment that EXCEEDS the safety limit ($2,500.00)
        exceed_res = await client.post(f"/api/v1/crm/clients/{client_id}/generate-replenishment", json={
            "items_summary": "10x Turbine Seals & Hydraulic Gaskets",
            "amount": 2500.00
        }, headers=headers)
        assert exceed_res.status_code == 200
        exceed_data = exceed_res.json()
        # Must NOT auto-charge because $2500 > $1000 limit
        assert exceed_data["auto_charged"] is False
        exceed_sale_id = exceed_data["sale_id"]

        async with AsyncSessionLocal() as db:
            s_exceed = await db.get(ClientSale, exceed_sale_id)
            assert s_exceed.payment_status == "unpaid"

        # 5. Now update auto-charge limit to $5,000.00
        await client.post(f"/api/v1/crm/clients/{client_id}/payment-method/auto-charge", json={
            "enabled": True,
            "limit": 5000.00
        }, headers=headers)

        # 6. Trigger replenishment for the existing pending sale: now it falls within limit!
        retry_res = await client.post(f"/api/v1/crm/clients/{client_id}/generate-replenishment", headers=headers)
        assert retry_res.status_code == 200
        retry_data = retry_res.json()
        assert retry_data["auto_charged"] is True
        assert retry_data["sale_id"] == exceed_sale_id

        # Verify sale is now paid and completed
        async with AsyncSessionLocal() as db:
            s_paid = await db.get(ClientSale, exceed_sale_id)
            assert s_paid.payment_status == "paid"
            assert s_paid.status == "completed"

            # Check next_reorder_date has advanced by ~21 days
            c_after = await db.get(ClientAccount, client_id)
            now = datetime.now(timezone.utc)
            days_ahead = (c_after.next_reorder_date.date() - now.date()).days
            assert 19 <= days_ahead <= 22
