import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
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
async def test_generate_and_get_portal_link():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register test tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "owner@pacificsupply.example",
            "password": "SecurePassword123!",
            "full_name": "Marcus Vance",
            "organization_name": "Pacific Supply Network"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Create client account
        c_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Evergreen Timber & Milling",
            "contact_first_name": "Douglas",
            "contact_last_name": "Fir",
            "contact_email": "doug@evergreentimber.example",
            "contact_phone": "+1 (555) 778-9900",
            "reorder_cadence_days": 30,
            "status": "active"
        }, headers=headers)
        assert c_res.status_code == 200
        client_id = c_res.json()["id"]

        # 3. Generate portal link
        link_res = await client.post(f"/api/v1/crm/clients/{client_id}/portal-link", headers=headers)
        assert link_res.status_code == 200
        link_data = link_res.json()
        assert link_data["portal_access_token"].startswith("pt_")
        assert link_data["portal_path"] == f"/portal/{link_data['portal_access_token']}"
        assert f"/portal/{link_data['portal_access_token']}" in link_data["full_portal_url"]
        portal_token = link_data["portal_access_token"]

        # 4. Verify consecutive request returns the same stable portal token
        link_res2 = await client.post(f"/api/v1/crm/clients/{client_id}/portal-link", headers=headers)
        assert link_res2.status_code == 200
        assert link_res2.json()["portal_access_token"] == portal_token

@pytest.mark.asyncio
async def test_customer_portal_session_loader_and_security():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant and client
        reg = await client.post("/api/v1/auth/register", json={
            "email": "admin@redwoodmfg.example",
            "password": "SecurePassword123!",
            "full_name": "Arthur Pendelton",
            "organization_name": "Redwood Manufacturing"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # Set white-label branding
        await client.put("/api/v1/orgs/settings", json={
            "brand_name": "Redwood Precision Logistics",
            "support_email": "ops@redwoodprecision.example",
            "support_phone": "+1 (888) 733-9663"
        }, headers=headers)

        c_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Sequoia Advanced Robotics",
            "contact_first_name": "Elena",
            "contact_last_name": "Rostova",
            "contact_email": "elena@sequoiarobotics.example",
            "reorder_cadence_days": 21,
            "status": "active"
        }, headers=headers)
        client_id = c_res.json()["id"]

        link_res = await client.post(f"/api/v1/crm/clients/{client_id}/portal-link", headers=headers)
        portal_token = link_res.json()["portal_access_token"]

        # 2. Public / Passwordless session access with valid token
        sess_res = await client.get(f"/api/v1/portal/session/{portal_token}")
        assert sess_res.status_code == 200
        data = sess_res.json()
        assert data["tenant"]["brand_name"] == "Redwood Precision Logistics"
        assert data["tenant"]["support_email"] == "ops@redwoodprecision.example"
        assert data["account"]["account_name"] == "Sequoia Advanced Robotics"
        assert data["account"]["reorder_cadence_days"] == 21
        assert data["payment_method"]["has_payment_method_on_file"] is False

        # 3. Invalid token returns 404
        bad_res = await client.get("/api/v1/portal/session/pt_invalid_token_99999")
        assert bad_res.status_code == 404
        assert "Invalid or expired" in bad_res.json()["detail"]

@pytest.mark.asyncio
async def test_customer_update_cadence_and_snooze():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant and client
        reg = await client.post("/api/v1/auth/register", json={
            "email": "director@cascadeind.example",
            "password": "SecurePassword123!",
            "full_name": "Clara Oswald",
            "organization_name": "Cascade Industrial Dist"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        c_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Olympic Heavy Machinery",
            "contact_first_name": "Grant",
            "contact_last_name": "Sterling",
            "contact_email": "grant@olympicmachinery.example",
            "reorder_cadence_days": 30,
            "status": "active"
        }, headers=headers)
        client_id = c_res.json()["id"]

        link_res = await client.post(f"/api/v1/crm/clients/{client_id}/portal-link", headers=headers)
        portal_token = link_res.json()["portal_access_token"]

        # 2. Customer updates cadence to 45 days
        cadence_res = await client.post(f"/api/v1/portal/session/{portal_token}/cadence", json={
            "reorder_cadence_days": 45
        })
        assert cadence_res.status_code == 200
        assert cadence_res.json()["reorder_cadence_days"] == 45

        async with AsyncSessionLocal() as db:
            c = await db.get(ClientAccount, client_id)
            assert c.reorder_cadence_days == 45

        # 3. Customer snoozes restock by 14 days
        snooze_res = await client.post(f"/api/v1/portal/session/{portal_token}/cadence", json={
            "snooze_days": 14
        })
        assert snooze_res.status_code == 200
        assert snooze_res.json()["next_reorder_date"] is not None

        async with AsyncSessionLocal() as db:
            c2 = await db.get(ClientAccount, client_id)
            now = datetime.now(timezone.utc)
            days_diff = (c2.next_reorder_date.date() - now.date()).days
            assert days_diff >= 13

@pytest.mark.asyncio
async def test_customer_manage_stored_card():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant and client
        reg = await client.post("/api/v1/auth/register", json={
            "email": "billing@glaciercold.example",
            "password": "SecurePassword123!",
            "full_name": "Viktor Frost",
            "organization_name": "Glacier Cold Supply"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        c_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Polar Freight Logistics",
            "contact_first_name": "Viktor",
            "contact_last_name": "Frost",
            "contact_email": "billing@glaciercold.example",
            "reorder_cadence_days": 30,
            "status": "active"
        }, headers=headers)
        client_id = c_res.json()["id"]

        link_res = await client.post(f"/api/v1/crm/clients/{client_id}/portal-link", headers=headers)
        portal_token = link_res.json()["portal_access_token"]

        # 2. Customer authorizes and attaches a corporate card from the portal
        card_res = await client.post(f"/api/v1/portal/session/{portal_token}/payment-method", json={
            "card_brand": "amex",
            "card_last4": "3007",
            "enable_auto_charge": True,
            "auto_charge_limit": 8000.0
        })
        assert card_res.status_code == 200
        card_data = card_res.json()
        assert card_data["has_payment_method_on_file"] is True
        assert card_data["card_brand"] == "amex"
        assert card_data["card_last4"] == "3007"
        assert card_data["auto_charge_enabled"] is True
        assert card_data["auto_charge_limit"] == 8000.0

        # Verify in DB
        async with AsyncSessionLocal() as db:
            c = await db.get(ClientAccount, client_id)
            assert c.has_payment_method_on_file is True
            assert c.card_last4 == "3007"

        # 3. Customer detaches card
        detach_res = await client.delete(f"/api/v1/portal/session/{portal_token}/payment-method")
        assert detach_res.status_code == 200
        assert detach_res.json()["has_payment_method_on_file"] is False

        async with AsyncSessionLocal() as db:
            c2 = await db.get(ClientAccount, client_id)
            assert c2.has_payment_method_on_file is False
            assert c2.auto_charge_enabled is False

@pytest.mark.asyncio
async def test_customer_accelerate_restock_now():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant and client
        reg = await client.post("/api/v1/auth/register", json={
            "email": "ops@orbitalsupply.example",
            "password": "SecurePassword123!",
            "full_name": "Neil Armstrong Jr",
            "organization_name": "Orbital Supply Hub"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        c_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Apex Space Launch Dynamics",
            "contact_first_name": "Neil",
            "contact_last_name": "Armstrong",
            "contact_email": "ops@orbitalsupply.example",
            "reorder_cadence_days": 30,
            "status": "active"
        }, headers=headers)
        client_id = c_res.json()["id"]

        link_res = await client.post(f"/api/v1/crm/clients/{client_id}/portal-link", headers=headers)
        portal_token = link_res.json()["portal_access_token"]

        # 2. Attach stored card with auto-charge enabled
        await client.post(f"/api/v1/portal/session/{portal_token}/payment-method", json={
            "card_brand": "visa",
            "card_last4": "4242",
            "enable_auto_charge": True,
            "auto_charge_limit": 10000.0
        })

        # 3. Customer clicks "Ship Restock Now" (accelerate-restock)
        accel_res = await client.post(f"/api/v1/portal/session/{portal_token}/accelerate-restock")
        assert accel_res.status_code == 200
        accel_data = accel_res.json()
        assert accel_data["success"] is True
        assert accel_data["order_number"].startswith("REP-")
        assert accel_data["auto_charged"] is True

        # Verify sale is recorded and paid
        order_num = accel_data["order_number"]
        async with AsyncSessionLocal() as db:
            s_stmt = select(ClientSale).where(ClientSale.order_number == order_num)
            s_res = await db.execute(s_stmt)
            sale = s_res.scalar_one_or_none()
            assert sale is not None
            assert sale.payment_status == "paid"
            assert sale.status == "completed"

            # Check next_reorder_date has advanced ~30 days
            c_after = await db.get(ClientAccount, client_id)
            now = datetime.now(timezone.utc)
            days_ahead = (c_after.next_reorder_date.date() - now.date()).days
            assert 28 <= days_ahead <= 31

@pytest.mark.asyncio
async def test_portal_html_page_rendering():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Test loading the HTML portal endpoint
        res = await client.get("/portal/pt_demo_sample_token_1234")
        assert res.status_code == 200
        assert "Customer Account &amp; Replenishment Portal" in res.text
        assert "pt_demo_sample_token_1234" in res.text
        assert "Ship Restock Now" in res.text
