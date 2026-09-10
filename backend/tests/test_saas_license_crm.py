import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.crm import ClientAccount, SaaSLicense, SaaSExpansionProposal, ClientSale
from app.models.hitl import HumanAssistanceRequest
from app.services.saas_license_service import saas_license_service

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_saas_license_provisioning_and_key_generation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register organization & user
        reg = await client.post("/api/v1/auth/register", json={
            "email": "saasadmin@cloudflow.example",
            "password": "Password123!",
            "full_name": "Marcus Vance",
            "organization_name": "CloudFlow SaaS Inc"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Create a Lead and convert it to a Client Account
        lead_res = await client.post("/api/v1/crm/leads", headers=headers, json={
            "company_name": "Apex Neural Labs",
            "company_domain": "apexneural.io",
            "contact_first_name": "Elena",
            "contact_last_name": "Rostova",
            "contact_email": "elena@apexneural.io"
        })
        assert lead_res.status_code == 200
        lead_id = lead_res.json()["id"]

        conv_res = await client.post(f"/api/v1/crm/leads/{lead_id}/convert-to-client", headers=headers, json={
            "account_tier": "enterprise",
            "reorder_cadence_days": 30,
            "initial_order_amount": 2500.0,
            "initial_order_items": "Apex Enterprise Pilot"
        })
        assert conv_res.status_code == 200
        client_id = conv_res.json()["id"]

        # 3. Provision a SaaS License for this client
        prov_res = await client.post("/api/v1/saas-licenses", headers=headers, json={
            "client_id": client_id,
            "product_name": "Apex Autonomous AI Platform",
            "plan_tier": "enterprise",
            "billing_interval": "annual",
            "licensed_seats": 50,
            "seat_unit_price": 60.0,
            "monthly_quota_units": 250000,
            "overage_allowed": True,
            "overage_unit_rate": 0.04,
            "auto_renew": True,
            "notes": "Enterprise tier provisioned for Apex Neural Labs"
        })
        assert prov_res.status_code == 201
        data = prov_res.json()

        # Assert key format and MRR/ARR
        assert data["license_key"].startswith("LIC-ENT-")
        assert data["license_token"].startswith("token_v1_")
        assert data["plan_tier"] == "enterprise"
        assert data["licensed_seats"] == 50
        assert data["seat_unit_price"] == 60.0
        assert data["mrr"] == 3000.0  # 50 * $60
        assert data["arr"] == 36000.0  # 3000 * 12
        assert data["health_score"] >= 80
        assert data["churn_risk_level"] == "healthy"
        assert data["client_name"] == "Apex Neural Labs"
        assert data["days_until_renewal"] >= 360

@pytest.mark.asyncio
async def test_saas_telemetry_ingestion_and_health_scoring():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register and setup
        reg = await client.post("/api/v1/auth/register", json={
            "email": "ops@streamline.example",
            "password": "Password123!",
            "full_name": "Devin Torres",
            "organization_name": "Streamline Tech"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        lead = (await client.post("/api/v1/crm/leads", headers=headers, json={
            "company_name": "Nova BioSystems",
            "contact_first_name": "Liam",
            "contact_last_name": "Neale",
            "contact_email": "liam@novabio.example"
        })).json()

        cl = (await client.post(f"/api/v1/crm/leads/{lead['id']}/convert-to-client", headers=headers, json={
            "account_tier": "pro"
        })).json()

        lic = (await client.post("/api/v1/saas-licenses", headers=headers, json={
            "client_id": cl["id"],
            "plan_tier": "pro",
            "licensed_seats": 100,
            "seat_unit_price": 40.0
        })).json()
        lic_id = lic["id"]

        # 2. Ingest low telemetry (10 out of 100 seats = 10% utilization -> churn risk)
        tel_low = await client.post(f"/api/v1/saas-licenses/{lic_id}/telemetry", headers=headers, json={
            "active_seats": 10,
            "quota_used": 5000
        })
        assert tel_low.status_code == 200
        low_data = tel_low.json()
        assert low_data["active_seats_used"] == 10
        assert low_data["seat_utilization_pct"] == 10.0
        assert low_data["health_score"] < 70
        assert low_data["churn_risk_level"] in ("monitor", "at_risk", "critical")
        assert "Severely low seat utilization" in low_data["health_rationale"]

        # 3. Ingest healthy telemetry (85 out of 100 seats = 85% optimal adoption)
        tel_healthy = await client.post(f"/api/v1/saas-licenses/{lic_id}/telemetry", headers=headers, json={
            "active_seats": 85,
            "quota_used": 75000
        })
        assert tel_healthy.status_code == 200
        healthy_data = tel_healthy.json()
        assert healthy_data["active_seats_used"] == 85
        assert healthy_data["seat_utilization_pct"] == 85.0
        assert healthy_data["health_score"] >= 80
        assert healthy_data["churn_risk_level"] == "healthy"

@pytest.mark.asyncio
async def test_autonomous_license_expansion_and_hitl_guardrail():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "growth@hypergrowth.example",
            "password": "Password123!",
            "full_name": "Kylie Jenner",
            "organization_name": "HyperGrowth Ventures"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        lead = (await client.post("/api/v1/crm/leads", headers=headers, json={
            "company_name": "DataMatrix Corp",
            "contact_first_name": "Nate",
            "contact_last_name": "Foster",
            "contact_email": "nate@datamatrix.example"
        })).json()

        cl = (await client.post(f"/api/v1/crm/leads/{lead['id']}/convert-to-client", headers=headers, json={
            "account_tier": "pro"
        })).json()

        lic = (await client.post("/api/v1/saas-licenses", headers=headers, json={
            "client_id": cl["id"],
            "plan_tier": "pro",
            "licensed_seats": 40,
            "seat_unit_price": 50.0
        })).json()
        lic_id = lic["id"]

        # 2. Simulate high seat saturation (38 / 40 seats = 95%)
        await client.post(f"/api/v1/saas-licenses/{lic_id}/telemetry", headers=headers, json={
            "active_seats": 38,
            "quota_used": 60000
        })

        # 3. Run Autonomous Expansion Audit without custom discount (standard autonomous proposal)
        audit_res = await client.post("/api/v1/saas-licenses/expansion-audit", headers=headers)
        assert audit_res.status_code == 200
        audit_data = audit_res.json()

        assert audit_data["expansion_candidates_found"] >= 1
        prop = audit_data["proposals_generated"][0]
        assert prop["license_id"] == lic_id
        assert prop["seat_utilization_pct"] == 95.0
        assert prop["proposed_new_seats"] == 60  # 40 + 20 (+50%)
        assert prop["arr_delta"] > 0
        assert prop["requires_hitl"] is False
        assert "Subject: Scaling your" in prop["ai_drafted_outreach"]
        assert "DataMatrix Corp" in prop["ai_drafted_outreach"]

        # 4. Now run expansion audit requesting 25% discount (> 10% max threshold) -> verify HITL halt!
        hitl_audit = await client.post("/api/v1/saas-licenses/expansion-audit?requested_discount_pct=25.0", headers=headers)
        assert hitl_audit.status_code == 200
        hitl_data = hitl_audit.json()
        hitl_prop = hitl_data["proposals_generated"][0]
        assert hitl_prop["requires_hitl"] is True

        # Verify HumanAssistanceRequest was created in the database
        async with AsyncSessionLocal() as session:
            stmt = select(HumanAssistanceRequest).where(
                HumanAssistanceRequest.organization_id == org_id,
                HumanAssistanceRequest.trigger_reason == "policy_discount"
            )
            req_res = await session.execute(stmt)
            hitl_req = req_res.scalar_one_or_none()
            assert hitl_req is not None
            assert hitl_req.status == "pending"
            assert "25.0% discount" in hitl_req.situation_summary

@pytest.mark.asyncio
async def test_autonomous_renewal_and_stored_card_auto_charge():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "cfo@fintechsaas.example",
            "password": "Password123!",
            "full_name": "Rachel Zane",
            "organization_name": "Fintech SaaS Corp"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        lead = (await client.post("/api/v1/crm/leads", headers=headers, json={
            "company_name": "CyberDefense Systems",
            "contact_first_name": "Harvey",
            "contact_last_name": "Specter",
            "contact_email": "harvey@cyberdefense.example"
        })).json()

        cl = (await client.post(f"/api/v1/crm/leads/{lead['id']}/convert-to-client", headers=headers, json={
            "account_tier": "enterprise"
        })).json()
        client_id = cl["id"]

        # Attach stored card and enable auto-charge
        attach_res = await client.post(f"/api/v1/crm/clients/{client_id}/payment-method/attach", headers=headers, json={
            "card_brand": "visa",
            "card_last4": "4242",
            "enable_auto_charge": True
        })
        assert attach_res.status_code == 200

        # Provision SaaS license
        lic = (await client.post("/api/v1/saas-licenses", headers=headers, json={
            "client_id": client_id,
            "plan_tier": "enterprise",
            "billing_interval": "annual",
            "licensed_seats": 20,
            "seat_unit_price": 50.0,
            "auto_renew": True
        })).json()
        lic_id = lic["id"]

        # Manually backdate renewal_date to 10 days from now to simulate contract expiration
        async with AsyncSessionLocal() as session:
            stmt = select(SaaSLicense).where(SaaSLicense.id == lic_id)
            res = await session.execute(stmt)
            lic_record = res.scalar_one()
            lic_record.renewal_date = datetime.now(timezone.utc) + timedelta(days=10)
            await session.commit()

        # Run Autonomous Renewal Radar
        radar_res = await client.post("/api/v1/saas-licenses/renewal-radar?lookahead_days=30", headers=headers)
        assert radar_res.status_code == 200
        radar_data = radar_res.json()

        assert radar_data["expiring_soon_count"] >= 1
        renewed_item = next(i for i in radar_data["items"] if i["license_id"] == lic_id)
        assert renewed_item["auto_charged"] is True
        assert renewed_item["action_recommended"] == "Auto-Renewed & Charged Stored Card"

        # Verify renewal date was extended by 365 days
        async with AsyncSessionLocal() as session:
            stmt = select(SaaSLicense).where(SaaSLicense.id == lic_id)
            res = await session.execute(stmt)
            updated_lic = res.scalar_one()
            ren_date = updated_lic.renewal_date
            if ren_date.tzinfo is None:
                ren_date = ren_date.replace(tzinfo=timezone.utc)
            days_out = (ren_date - datetime.now(timezone.utc)).days
            assert days_out > 360

@pytest.mark.asyncio
async def test_order_filler_cloud_provisioning_bot_integration():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "devops@cloudops.example",
            "password": "Password123!",
            "full_name": "Alex Mercer",
            "organization_name": "CloudOps Solutions"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        lead = (await client.post("/api/v1/crm/leads", headers=headers, json={
            "company_name": "AeroDynamics Inc",
            "contact_first_name": "John",
            "contact_last_name": "Doe",
            "contact_email": "john@aerodynamics.example"
        })).json()

        cl = (await client.post(f"/api/v1/crm/leads/{lead['id']}/convert-to-client", headers=headers, json={
            "account_tier": "enterprise"
        })).json()

        lic = (await client.post("/api/v1/saas-licenses", headers=headers, json={
            "client_id": cl["id"],
            "plan_tier": "enterprise",
            "licensed_seats": 50
        })).json()
        lic_id = lic["id"]

        # Trigger Order Filler Agent for Cloud Provisioning
        prov_res = await client.post(f"/api/v1/saas-licenses/{lic_id}/provision-cloud", headers=headers, json={
            "cloud_provider": "amazon_aws",
            "resource_spec": "50 Virtual Containers & Enterprise Encryption Keys"
        })
        assert prov_res.status_code == 200
        prov_data = prov_res.json()

        assert prov_data["purchase_order_id"] is not None
        assert prov_data["po_number"].startswith("PO-")
        assert prov_data["provisioning_status"] == "provisioned_dispatched"
        assert prov_data["tracking_number"] is not None
        assert "Autonomous Cloud Provisioner dispatched" in prov_data["message"]

@pytest.mark.asyncio
async def test_saas_metrics_overview_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "metrics@metricorp.example",
            "password": "Password123!",
            "full_name": "Diana Prince",
            "organization_name": "MetriCorp International"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        lead = (await client.post("/api/v1/crm/leads", headers=headers, json={
            "company_name": "Vanguard Labs",
            "contact_first_name": "Bruce",
            "contact_last_name": "Wayne",
            "contact_email": "bruce@vanguard.example"
        })).json()

        cl = (await client.post(f"/api/v1/crm/leads/{lead['id']}/convert-to-client", headers=headers, json={
            "account_tier": "enterprise"
        })).json()

        await client.post("/api/v1/saas-licenses", headers=headers, json={
            "client_id": cl["id"],
            "plan_tier": "pro",
            "licensed_seats": 30,
            "seat_unit_price": 50.0
        })

        metrics_res = await client.get("/api/v1/saas-licenses/metrics/overview", headers=headers)
        assert metrics_res.status_code == 200
        m = metrics_res.json()

        assert m["total_licenses"] == 1
        assert m["active_licenses"] == 1
        assert m["total_licensed_seats"] == 30
        assert m["total_mrr"] == 1500.0  # 30 * $50
        assert m["total_arr"] == 18000.0  # 1500 * 12
        assert m["healthy_count"] == 1
