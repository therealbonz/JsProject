import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.crm import ClientAccount

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_replenishment_engine_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register test tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "procurement@wholesaledirect.example",
            "password": "Password123!",
            "full_name": "Marcus Director",
            "organization_name": "National Hardware & Supply"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Create client account with 30-day cadence
        client_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Highland Construction Materials",
            "contact_first_name": "Trevor",
            "contact_last_name": "Barnes",
            "contact_email": "trevor@highlandconstruction.example",
            "contact_phone": "+1 (555) 902-1144",
            "company_domain": "highlandconstruction.example",
            "industry": "Commercial Construction",
            "reorder_cadence_days": 30,
            "status": "active"
        }, headers=headers)
        assert client_res.status_code == 200
        client_data = client_res.json()
        client_id = client_data["id"]

        # 3. Manually set next_reorder_date to past due (yesterday) in database
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        async with AsyncSessionLocal() as db:
            c = await db.get(ClientAccount, client_id)
            c.next_reorder_date = yesterday
            await db.commit()

        # 4. Check due replenishments endpoint
        due_res = await client.get("/api/v1/crm/replenishments/due", headers=headers)
        assert due_res.status_code == 200
        due_data = due_res.json()
        assert due_data["count"] >= 1
        due_client = next(c for c in due_data["due_clients"] if c["client_id"] == client_id)
        assert due_client["account_name"] == "Highland Construction Materials"
        assert due_client["urgency"] == "overdue"
        assert due_client["reorder_cadence_days"] == 30

        # 5. Generate replenishment proposal for client
        prop_res = await client.post(f"/api/v1/crm/clients/{client_id}/generate-replenishment", json={
            "items_summary": "15x Heavy Duty Pallet Wrap Rolls & Steel Strapping",
            "amount": 1250.00
        }, headers=headers)
        assert prop_res.status_code == 200
        prop_data = prop_res.json()
        assert prop_data["order_number"].startswith("REP-")
        assert prop_data["amount"] == 1250.00
        assert "/checkout/pay/" in prop_data["checkout_url"]
        sale_id = prop_data["sale_id"]

        # Check hosted checkout page loads with this replenishment session
        checkout_url = prop_data["checkout_url"]
        checkout_page = await client.get(checkout_url)
        assert checkout_page.status_code == 200
        assert "Complete Secure Payment" in checkout_page.text

        # 6. Simulate payment confirmation for replenishment order
        sim_res = await client.post(f"/api/v1/crm/sales/{sale_id}/simulate-payment", headers=headers)
        assert sim_res.status_code == 200
        sim_data = sim_res.json()
        assert sim_data["payment_status"] == "paid"
        assert sim_data["auto_fulfillment_triggered"] is True
        assert sim_data["purchase_order"] is not None

        # 7. Verify client's next_reorder_date has advanced by 30 days
        async with AsyncSessionLocal() as db:
            c_after = await db.get(ClientAccount, client_id)
            now = datetime.now(timezone.utc)
            # Reorder date should now be ~30 days in the future
            days_ahead = (c_after.next_reorder_date.date() - now.date()).days
            assert 28 <= days_ahead <= 31

        # 8. Test snooze replenishment endpoint
        snooze_res = await client.post(f"/api/v1/crm/clients/{client_id}/snooze-replenishment", json={
            "snooze_days": 10
        }, headers=headers)
        assert snooze_res.status_code == 200
        snooze_data = snooze_res.json()
        assert snooze_data["snoozed_days"] == 10

        async with AsyncSessionLocal() as db:
            c_snoozed = await db.get(ClientAccount, client_id)
            days_ahead_snoozed = (c_snoozed.next_reorder_date.date() - now.date()).days
            assert 38 <= days_ahead_snoozed <= 41

        # 9. Test bulk process-due endpoint
        # Create a second client due today
        c2_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Apex Mining Supplies",
            "contact_first_name": "Sarah",
            "contact_last_name": "Connor",
            "contact_email": "sarah@apexmining.example",
            "reorder_cadence_days": 15,
            "status": "active"
        }, headers=headers)
        assert c2_res.status_code == 200
        c2_id = c2_res.json()["id"]

        async with AsyncSessionLocal() as db:
            c2 = await db.get(ClientAccount, c2_id)
            c2.next_reorder_date = datetime.now(timezone.utc)
            await db.commit()

        bulk_res = await client.post("/api/v1/crm/replenishments/process-due", headers=headers)
        assert bulk_res.status_code == 200
        bulk_data = bulk_res.json()
        assert bulk_data["success"] is True
        assert bulk_data["generated_count"] >= 1
        assert any(p["client_id"] == c2_id for p in bulk_data["proposals"])
