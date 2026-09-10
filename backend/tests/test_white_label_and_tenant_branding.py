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
async def test_white_label_branding_and_tenant_settings():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register new tenant
        reg_res = await client.post("/api/v1/auth/register", json={
            "email": "owner@apexsupply.com",
            "password": "Password123!",
            "full_name": "Apex Administrator",
            "organization_name": "Apex Wholesale Distro"
        })
        assert reg_res.status_code == 200
        reg_data = reg_res.json()
        token = reg_data["access_token"]
        org_id = reg_data["organization_id"]
        auth_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Get initial settings
        get_res = await client.get("/api/v1/orgs/settings", headers=auth_headers)
        assert get_res.status_code == 200
        initial_data = get_res.json()
        assert initial_data["name"] == "Apex Wholesale Distro"
        assert initial_data["has_stripe_secret"] is False

        # 3. Update Organization White-Label Branding & Stripe credentials
        update_payload = {
            "name": "Apex Distribution Group",
            "brand_name": "Apex Freight & Distribution",
            "brand_logo_url": "https://apex.example.com/logo.png",
            "brand_accent_color": "#0ea5e9",
            "support_email": "help@apexdistro.com",
            "support_phone": "+1 800-555-APEX",
            "tracking_portal_notice": "Priority freight dispatches daily at 2 PM MST.",
            "custom_footer_text": "Apex Distribution Group - ISO 9001 Certified",
            "stripe_publishable_key": "pk_test_apex_pub_123456789",
            "stripe_secret_key": "sk_test_apex_secret_key_998877",
            "stripe_webhook_secret": "whsec_apex_test_signing_secret"
        }
        put_res = await client.put("/api/v1/orgs/settings", json=update_payload, headers=auth_headers)
        assert put_res.status_code == 200
        put_data = put_res.json()
        assert put_data["brand_name"] == "Apex Freight & Distribution"
        assert put_data["brand_accent_color"] == "#0ea5e9"
        assert put_data["support_email"] == "help@apexdistro.com"
        assert put_data["support_phone"] == "+1 800-555-APEX"
        assert put_data["tracking_portal_notice"] == "Priority freight dispatches daily at 2 PM MST."
        assert put_data["has_stripe_secret"] is True
        assert put_data["is_payment_configured"] is True
        assert "••••" in put_data["masked_stripe_secret"]
        assert "sk_test_apex_secret_key_998877" not in put_data["masked_stripe_secret"]

        # 4. Verify unauthenticated public branding endpoint
        public_brand_res = await client.get(f"/api/v1/orgs/public-brand/{org_id}")
        assert public_brand_res.status_code == 200
        brand_data = public_brand_res.json()
        assert brand_data["brand_name"] == "Apex Freight & Distribution"
        assert brand_data["brand_accent_color"] == "#0ea5e9"
        assert brand_data["support_email"] == "help@apexdistro.com"
        assert "stripe_secret_key" not in brand_data

        # 5. Create a client account and sale to test tracking & checkout branding
        client_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Rocky Mountain Hardware",
            "contact_first_name": "Sam",
            "contact_last_name": "Miller",
            "contact_email": "sam@rockymountain.example",
            "contact_phone": "+1 555-908-1122",
            "company_domain": "rockymountain.example",
            "industry": "Retail Hardware",
            "reorder_cadence_days": 30,
            "status": "active"
        }, headers=auth_headers)
        assert client_res.status_code == 200
        client_id = client_res.json()["id"]

        sale_res = await client.post(f"/api/v1/crm/clients/{client_id}/sales", json={
            "items_summary": "100x Industrial Grade Fasteners Box",
            "amount": 850.00,
            "payment_method": "stripe",
            "auto_fulfill_on_payment": True,
            "customer_email": "buyer@rockymountain.com"
        }, headers=auth_headers)
        assert sale_res.status_code == 200
        sale_data = sale_res.json()
        sale_id = sale_data["id"]
        order_number = sale_data["order_number"]

        # 6. Verify public order tracking API includes tenant's custom brand
        track_res = await client.get(f"/api/v1/public/tracking/{order_number}")
        assert track_res.status_code == 200
        track_data = track_res.json()
        assert track_data["brand_name"] == "Apex Freight & Distribution"
        assert track_data["brand_accent_color"] == "#0ea5e9"
        assert track_data["support_email"] == "help@apexdistro.com"
        assert track_data["support_phone"] == "+1 800-555-APEX"
        assert track_data["tracking_portal_notice"] == "Priority freight dispatches daily at 2 PM MST."

        # Verify tracking HTML portal renders
        track_html_res = await client.get(f"/track/{order_number}")
        assert track_html_res.status_code == 200
        assert "<html" in track_html_res.text.lower()

        # 7. Create checkout session and verify public checkout session API
        checkout_res = await client.post(f"/api/v1/crm/sales/{sale_id}/create-checkout", json={
            "customer_email": "buyer@rockymountain.com"
        }, headers=auth_headers)
        assert checkout_res.status_code == 200
        checkout_data = checkout_res.json()
        session_id = checkout_data["session_id"]

        public_checkout_res = await client.get(f"/api/v1/public/checkout/{session_id}")
        assert public_checkout_res.status_code == 200
        pub_check_data = public_checkout_res.json()
        assert pub_check_data["brand_name"] == "Apex Freight & Distribution"
        assert pub_check_data["brand_accent_color"] == "#0ea5e9"
        assert pub_check_data["support_email"] == "help@apexdistro.com"

        # Verify hosted checkout HTML portal renders
        html_checkout_res = await client.get(f"/checkout/pay/{session_id}")
        assert html_checkout_res.status_code == 200
        assert "<html" in html_checkout_res.text.lower()

        # 8. Multi-tenant isolation: Register Tenant B and verify isolation
        reg_b = await client.post("/api/v1/auth/register", json={
            "email": "director@beaconlogistics.com",
            "password": "Password123!",
            "full_name": "Beacon Director",
            "organization_name": "Beacon Logistics LLC"
        })
        assert reg_b.status_code == 200
        data_b = reg_b.json()
        headers_b = {"Authorization": f"Bearer {data_b['access_token']}", "X-Organization-Id": data_b["organization_id"]}

        # Update Tenant B with distinct branding
        await client.put("/api/v1/orgs/settings", json={
            "brand_name": "Beacon Global Cargo",
            "brand_accent_color": "#10b981"
        }, headers=headers_b)

        # Check Tenant B brand
        brand_b_res = await client.get(f"/api/v1/orgs/public-brand/{data_b['organization_id']}")
        assert brand_b_res.json()["brand_name"] == "Beacon Global Cargo"
        assert brand_b_res.json()["brand_accent_color"] == "#10b981"

        # Re-check Tenant A brand: must still be Apex Freight & Distribution
        brand_a_res = await client.get(f"/api/v1/orgs/public-brand/{org_id}")
        assert brand_a_res.json()["brand_name"] == "Apex Freight & Distribution"
        assert brand_a_res.json()["brand_accent_color"] == "#0ea5e9"
