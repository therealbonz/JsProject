import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.crm import ClientAccount, SaaSLicense, ClientSale
from app.models.metered_billing import MeteredUsageRecord, MeteredBillingInvoice
from app.models.developer import ApiKey, WebhookSubscription, WebhookDeliveryLog

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_metric_catalog_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/v1/metered-billing/catalog")
        assert res.status_code == 200
        catalog = res.json()
        assert len(catalog) >= 5
        metrics = [item["metric_name"] for item in catalog]
        assert "api_calls" in metrics
        assert "ai_agent_runs" in metrics
        assert "procurement_orders" in metrics
        assert "edi_transactions" in metrics
        assert "storage_mb" in metrics


@pytest.mark.asyncio
async def test_record_usage_and_idempotency():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register organization & user
        reg = await client.post("/api/v1/auth/register", json={
            "email": "billingadmin@enterprise.example",
            "password": "Password123!",
            "full_name": "Sarah Connor",
            "organization_name": "Cyberdyne Systems"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Create Lead and convert to Client Account
        lead_res = await client.post("/api/v1/crm/leads", headers=headers, json={
            "company_name": "Skynet Logistics",
            "company_domain": "skynet.ai",
            "contact_first_name": "John",
            "contact_last_name": "Doe",
            "contact_email": "john@skynet.ai"
        })
        assert lead_res.status_code == 200
        lead_id = lead_res.json()["id"]

        conv_res = await client.post(f"/api/v1/crm/leads/{lead_id}/convert-to-client", headers=headers, json={
            "account_tier": "starter",
            "reorder_cadence_days": 30,
            "initial_order_amount": 1000.0,
            "initial_order_items": "Starter License Setup"
        })
        assert conv_res.status_code == 200
        client_id = conv_res.json()["id"]

        # 3. Provision Starter SaaS License
        prov_res = await client.post("/api/v1/saas-licenses", headers=headers, json={
            "client_id": client_id,
            "plan_tier": "starter",
            "product_name": "Logistics AI Starter",
            "billing_interval": "monthly",
            "licensed_seats": 5,
            "seat_unit_price": 40.0,
            "monthly_quota_units": 25000,
            "auto_renew": True
        })
        assert prov_res.status_code in (200, 201)
        license_id = prov_res.json()["id"]

        # 4. Ingest metered usage with idempotency key
        evt_res1 = await client.post("/api/v1/metered-billing/usage", headers=headers, json={
            "license_id": license_id,
            "metric_name": "api_calls",
            "quantity": 5000.0,
            "idempotency_key": "evt-skynet-001",
            "source": "api_gateway",
            "metadata": {"endpoint": "/v1/dispatch"}
        })
        assert evt_res1.status_code == 201
        rec1 = evt_res1.json()
        assert rec1["quantity"] == 5000.0
        assert rec1["idempotency_key"] == "evt-skynet-001"

        # 5. Ingest duplicate event with same idempotency key
        evt_res2 = await client.post("/api/v1/metered-billing/usage", headers=headers, json={
            "license_id": license_id,
            "metric_name": "api_calls",
            "quantity": 5000.0,
            "idempotency_key": "evt-skynet-001",
            "source": "api_gateway"
        })
        assert evt_res2.status_code == 201
        rec2 = evt_res2.json()
        # ID should be identical (deduplicated)
        assert rec1["id"] == rec2["id"]


@pytest.mark.asyncio
async def test_batch_usage_and_overage_calculations():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register organization & user
        reg = await client.post("/api/v1/auth/register", json={
            "email": "meteradmin@acme.example",
            "password": "Password123!",
            "full_name": "Miles Dyson",
            "organization_name": "Neural Tech"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Setup Client & Starter License
        lead = (await client.post("/api/v1/crm/leads", headers=headers, json={
            "company_name": "Omni Corp",
            "company_domain": "omni.com",
            "contact_first_name": "Bob",
            "contact_last_name": "Morton",
            "contact_email": "bob@omni.com"
        })).json()

        client_acc = (await client.post(f"/api/v1/crm/leads/{lead['id']}/convert-to-client", headers=headers, json={
            "account_tier": "starter"
        })).json()

        lic = (await client.post("/api/v1/saas-licenses", headers=headers, json={
            "client_id": client_acc["id"],
            "plan_tier": "starter",
            "monthly_quota_units": 25000
        })).json()
        license_id = lic["id"]

        # Starter Tier allowances:
        # api_calls: 25,000 incl, overage rate: $0.002
        # ai_agent_runs: 100 incl, overage rate: $0.15
        # procurement_orders: 20 incl, overage rate: $2.00

        # Ingest batch with overages:
        # api_calls: 35,000 consumed -> 10,000 overage * $0.002 = $20.00
        # ai_agent_runs: 150 consumed -> 50 overage * $0.15 = $7.50
        # procurement_orders: 15 consumed -> 0 overage (under 20 included) = $0.00
        batch_res = await client.post("/api/v1/metered-billing/usage/batch", headers=headers, json={
            "license_id": license_id,
            "events": [
                {"license_id": license_id, "metric_name": "api_calls", "quantity": 20000.0},
                {"license_id": license_id, "metric_name": "api_calls", "quantity": 15000.0},
                {"license_id": license_id, "metric_name": "ai_agent_runs", "quantity": 150.0},
                {"license_id": license_id, "metric_name": "procurement_orders", "quantity": 15.0}
            ]
        })
        assert batch_res.status_code == 201
        assert len(batch_res.json()) == 4

        # Verify summary
        sum_res = await client.get(f"/api/v1/metered-billing/licenses/{license_id}/summary", headers=headers)
        assert sum_res.status_code == 200
        data = sum_res.json()

        metrics_map = {m["metric_name"]: m for m in data["metrics"]}
        assert metrics_map["api_calls"]["consumed_units"] == 35000.0
        assert metrics_map["api_calls"]["overage_units"] == 10000.0
        assert metrics_map["api_calls"]["accrued_charge"] == 20.0

        assert metrics_map["ai_agent_runs"]["consumed_units"] == 150.0
        assert metrics_map["ai_agent_runs"]["overage_units"] == 50.0
        assert metrics_map["ai_agent_runs"]["accrued_charge"] == 7.50

        assert metrics_map["procurement_orders"]["consumed_units"] == 15.0
        assert metrics_map["procurement_orders"]["overage_units"] == 0.0
        assert metrics_map["procurement_orders"]["accrued_charge"] == 0.0

        # Total accrued overage = $20.00 + $7.50 = $27.50
        assert data["total_accrued_overage"] == 27.50


@pytest.mark.asyncio
async def test_settle_billing_cycle_with_stored_card_auto_charge():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register organization & user
        reg = await client.post("/api/v1/auth/register", json={
            "email": "fintech@apex.example",
            "password": "Password123!",
            "full_name": "Claire Redfield",
            "organization_name": "Apex Global"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Setup client
        lead = (await client.post("/api/v1/crm/leads", headers=headers, json={
            "company_name": "Umbrella Corp",
            "company_domain": "umbrella.com",
            "contact_first_name": "Albert",
            "contact_last_name": "Wesker",
            "contact_email": "albert@umbrella.com"
        })).json()

        client_acc = (await client.post(f"/api/v1/crm/leads/{lead['id']}/convert-to-client", headers=headers, json={
            "account_tier": "starter"
        })).json()
        client_id = client_acc["id"]

        lic = (await client.post("/api/v1/saas-licenses", headers=headers, json={
            "client_id": client_id,
            "plan_tier": "starter",
            "monthly_quota_units": 25000
        })).json()
        license_id = lic["id"]

        # 3. Attach stored payment method on file with auto-charge enabled
        card_res = await client.post(f"/api/v1/crm/clients/{client_id}/payment-method/attach", headers=headers, json={
            "card_brand": "visa",
            "card_last4": "4242",
            "payment_method_type": "card",
            "enable_auto_charge": True,
            "auto_charge_limit": 500.0
        })
        assert card_res.status_code == 200
        assert card_res.json()["has_payment_method_on_file"] is True
        assert card_res.json()["auto_charge_enabled"] is True

        # 4. Ingest overage usage (10,000 overage API calls = $20.00)
        await client.post("/api/v1/metered-billing/usage", headers=headers, json={
            "license_id": license_id,
            "metric_name": "api_calls",
            "quantity": 35000.0
        })

        # 5. Settle cycle and auto-charge
        settle_res = await client.post(f"/api/v1/metered-billing/licenses/{license_id}/settle", headers=headers, json={
            "auto_charge": True,
            "notes": "End of cycle automated settlement"
        })
        assert settle_res.status_code == 200
        inv = settle_res.json()

        assert inv["status"] == "settled"
        assert inv["total_billed_amount"] == 20.0
        assert inv["payment_status"] == "paid"
        assert inv["payment_method"] == "card_on_file"
        assert inv["client_sale_id"] is not None
        assert "INV-METER-" in inv["invoice_number"]

        # 6. Verify invoice in list endpoint
        inv_list_res = await client.get(f"/api/v1/metered-billing/invoices?license_id={license_id}", headers=headers)
        assert inv_list_res.status_code == 200
        invoices = inv_list_res.json()
        assert len(invoices) == 1
        assert invoices[0]["id"] == inv["id"]

        # 7. Verify new cycle summary is reset
        summary_res = await client.get(f"/api/v1/metered-billing/licenses/{license_id}/summary", headers=headers)
        assert summary_res.status_code == 200
        assert summary_res.json()["total_accrued_overage"] == 0.0


@pytest.mark.asyncio
async def test_developer_api_key_usage_ingestion():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register organization & user
        reg = await client.post("/api/v1/auth/register", json={
            "email": "devadmin@platform.example",
            "password": "Password123!",
            "full_name": "Ada Lovelace",
            "organization_name": "Babbage Systems"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        user_headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Setup Client and License
        lead = (await client.post("/api/v1/crm/leads", headers=user_headers, json={
            "company_name": "Analytical Engine Co",
            "company_domain": "analytical.io",
            "contact_first_name": "Charles",
            "contact_last_name": "Babbage",
            "contact_email": "charles@analytical.io"
        })).json()

        client_acc = (await client.post(f"/api/v1/crm/leads/{lead['id']}/convert-to-client", headers=user_headers, json={
            "account_tier": "pro"
        })).json()

        lic = (await client.post("/api/v1/saas-licenses", headers=user_headers, json={
            "client_id": client_acc["id"],
            "plan_tier": "pro"
        })).json()
        license_id = lic["id"]

        # 3. Create a Developer API Key
        key_res = await client.post("/api/v1/developer/keys", headers=user_headers, json={
            "key_name": "Production Telemetry Daemon",
            "scopes": ["*"]
        })
        assert key_res.status_code in (200, 201)
        raw_key = key_res.json()["api_key"]
        assert raw_key.startswith("jsp_live_")

        # 4. Ingest metered usage using ONLY the Developer API Key header (No Bearer token!)
        dev_headers = {
            "X-API-Key": raw_key,
            "X-Organization-Id": org_id
        }
        ingest_res = await client.post("/api/v1/metered-billing/usage", headers=dev_headers, json={
            "license_id": license_id,
            "metric_name": "edi_transactions",
            "quantity": 12.0,
            "source": "developer_daemon"
        })
        assert ingest_res.status_code == 201
        data = ingest_res.json()
        assert data["metric_name"] == "edi_transactions"
        assert data["quantity"] == 12.0


@pytest.mark.asyncio
async def test_webhook_dispatch_on_metered_settlement():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register organization & user
        reg = await client.post("/api/v1/auth/register", json={
            "email": "hookadmin@eventhub.example",
            "password": "Password123!",
            "full_name": "Grace Hopper",
            "organization_name": "Compiler Labs"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Subscribe to payment.succeeded and order.created webhooks
        sub_res = await client.post("/api/v1/developer/webhooks", headers=headers, json={
            "target_url": "https://webhook.site/metered-test",
            "description": "Metered Settlement Consumer",
            "events": ["order.created", "payment.succeeded"]
        })
        assert sub_res.status_code in (200, 201)

        # 3. Setup client & license
        lead = (await client.post("/api/v1/crm/leads", headers=headers, json={
            "company_name": "Cobol Corp",
            "company_domain": "cobol.org",
            "contact_first_name": "Grace",
            "contact_last_name": "Hopper",
            "contact_email": "hopper@cobol.org"
        })).json()

        client_acc = (await client.post(f"/api/v1/crm/leads/{lead['id']}/convert-to-client", headers=headers, json={
            "account_tier": "starter"
        })).json()

        lic = (await client.post("/api/v1/saas-licenses", headers=headers, json={
            "client_id": client_acc["id"],
            "plan_tier": "starter",
            "monthly_quota_units": 1000
        })).json()
        license_id = lic["id"]

        # 4. Attach card
        await client.post(f"/api/v1/crm/clients/{client_acc['id']}/payment-method/attach", headers=headers, json={
            "card_brand": "mastercard",
            "card_last4": "8888",
            "payment_method_type": "card",
            "enable_auto_charge": True
        })

        # 5. Ingest overage
        await client.post("/api/v1/metered-billing/usage", headers=headers, json={
            "license_id": license_id,
            "metric_name": "procurement_orders",
            "quantity": 25.0  # 20 incl, 5 overage @ $2.00 = $10.00
        })

        # 6. Settle
        settle = await client.post(f"/api/v1/metered-billing/licenses/{license_id}/settle", headers=headers, json={
            "auto_charge": True
        })
        assert settle.status_code == 200

        # 7. Verify WebhookDeliveryLogs were recorded
        async with AsyncSessionLocal() as db:
            logs_stmt = select(WebhookDeliveryLog).where(
                WebhookDeliveryLog.organization_id == org_id
            )
            logs = (await db.execute(logs_stmt)).scalars().all()
            # Should have recorded delivery attempts for order.created and payment.succeeded
            event_types = [l.event_type for l in logs]
            assert "order.created" in event_types
            assert "payment.succeeded" in event_types
