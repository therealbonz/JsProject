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
async def test_signup_page_rendering():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Root /signup route
        res = await client.get("/signup")
        assert res.status_code == 200
        assert "text/html" in res.headers["content-type"]
        html = res.text
        assert "Starter SDR" in html
        assert "Growth Team" in html
        assert "Executive Workforce" in html
        assert "$199" in html
        assert "$499" in html
        assert "$1,499" in html
        assert "org_name" in html
        assert "email" in html
        assert "password" in html

        # 2. Sub-path /JsProject/signup with plan query parameter
        res_sub = await client.get("/JsProject/signup?plan=executive")
        assert res_sub.status_code == 200
        assert "text/html" in res_sub.headers["content-type"]
        assert "Executive Workforce" in res_sub.text

@pytest.mark.asyncio
async def test_billing_plans_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for prefix in ["/api/v1/billing/plans", "/JsProject/api/v1/billing/plans"]:
            res = await client.get(prefix)
            assert res.status_code == 200
            plans = res.json()
            assert len(plans) == 3

            # Verify Starter Plan
            starter = next(p for p in plans if p["tier"] == "starter")
            assert starter["price"] == 199.0
            assert starter["seats"] == 2
            assert starter["monthly_touches"] == 1000
            assert starter["bots_count"] == 1

            # Verify Growth Plan
            growth = next(p for p in plans if p["tier"] == "growth")
            assert growth["price"] == 499.0
            assert growth["seats"] == 5
            assert growth["monthly_touches"] == 5000
            assert growth["bots_count"] == 3

            # Verify Executive Plan
            executive = next(p for p in plans if p["tier"] == "executive")
            assert executive["price"] == 1499.0
            assert executive["seats"] == 20
            assert executive["monthly_touches"] == 25000
            assert executive["bots_count"] == 6

@pytest.mark.asyncio
async def test_saas_checkout_simulation_provisions_growth_tenant():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "organization_name": "CloudScale Systems",
            "full_name": "Alex Mercer",
            "email": "alex.mercer@cloudscale.example",
            "password": "SecurePassword123!",
            "plan_tier": "growth"
        }
        res = await client.post("/api/v1/billing/saas-checkout-session", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["is_simulation"] is True
        assert data["plan_tier"] == "growth"
        assert data["organization_id"] is not None
        assert data["token"] is not None
        assert "console" in data["checkout_url"]

        token = data["token"]
        org_id = data["organization_id"]

        # Verify provisioned tenant can authenticate immediately
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
        me_res = await client.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["email"] == "alex.mercer@cloudscale.example"
        assert me_data["is_active"] is True

        # Verify active SaaSLicense was created for Growth tier
        lic_res = await client.get("/api/v1/saas-licenses", headers=headers)
        assert lic_res.status_code == 200
        licenses = lic_res.json()
        assert len(licenses) >= 1
        growth_lic = licenses[0]
        assert growth_lic["plan_tier"] == "growth"
        assert growth_lic["license_status"] == "active"
        assert growth_lic["mrr"] == 499.0
        assert growth_lic["licensed_seats"] == 5
        assert growth_lic["monthly_quota_units"] == 5000

@pytest.mark.asyncio
async def test_saas_checkout_simulation_provisions_executive_workforce():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "organization_name": "Apex Global Enterprises",
            "full_name": "Elena Rostova",
            "email": "elena@apexglobal.example",
            "password": "EnterprisePassword456!",
            "plan_tier": "executive"
        }
        res = await client.post("/api/v1/billing/saas-checkout-session", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["plan_tier"] == "executive"
        token = data["token"]
        org_id = data["organization_id"]

        # Verify active SaaSLicense was created for Executive tier with full 6-bot allocations
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
        lic_res = await client.get("/api/v1/saas-licenses", headers=headers)
        assert lic_res.status_code == 200
        licenses = lic_res.json()
        assert len(licenses) >= 1
        exec_lic = licenses[0]
        assert exec_lic["plan_tier"] == "executive"
        assert exec_lic["license_status"] == "active"
        assert exec_lic["mrr"] == 1499.0
        assert exec_lic["licensed_seats"] == 20
        assert exec_lic["monthly_quota_units"] == 25000

@pytest.mark.asyncio
async def test_saas_checkout_duplicate_email_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {
            "organization_name": "First Corp",
            "full_name": "Jordan Smith",
            "email": "jordan@firstcorp.example",
            "password": "ValidPassword123!",
            "plan_tier": "starter"
        }
        # First registration succeeds
        res1 = await client.post("/api/v1/billing/saas-checkout-session", json=payload)
        assert res1.status_code == 200

        # Duplicate registration fails with 400
        res2 = await client.post("/api/v1/billing/saas-checkout-session", json=payload)
        assert res2.status_code == 400
        assert "already exists" in res2.json()["detail"]

@pytest.mark.asyncio
async def test_landing_page_pricing_links_lead_to_signup():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/landing")
        assert res.status_code == 200
        html = res.text
        assert "signup?plan=starter" in html
        assert "signup?plan=growth" in html
        assert "signup?plan=executive" in html

@pytest.mark.asyncio
async def test_saas_webhook_idempotent_fulfillment():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        mock_webhook_payload = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_stripe_webhook_123",
                    "customer": "cus_test_999",
                    "subscription": "sub_test_888",
                    "metadata": {
                        "type": "saas_subscription",
                        "email": "webhook.founder@saasstartup.example",
                        "full_name": "Founder Bob",
                        "organization_name": "Webhook SaaS Inc",
                        "raw_password": "WebhookPassword789!",
                        "plan_tier": "growth"
                    }
                }
            }
        }
        res = await client.post("/api/v1/billing/saas-webhook", json=mock_webhook_payload)
        assert res.status_code == 200
        body = res.json()
        assert body["received"] is True
        assert body["status"] == "provisioned"

        # Re-sending the same webhook is idempotent
        res_repeat = await client.post("/api/v1/billing/saas-webhook", json=mock_webhook_payload)
        assert res_repeat.status_code == 200
        assert res_repeat.json()["status"] == "already_provisioned"
