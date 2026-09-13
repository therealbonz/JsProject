import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base
from app.services.voice_ai_service import VoiceAIService
from app.services.collateral_dispatch_service import CollateralDispatchService

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_collateral_templates_catalog():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/v1/collateral/templates")
        assert res.status_code == 200
        data = res.json()
        assert "templates" in data
        templates = data["templates"]
        assert len(templates) >= 3

        template_ids = [t["id"] for t in templates]
        assert "executive_briefing_letter" in template_ids
        assert "enterprise_postcard" in template_ids
        assert "autonomous_whitepaper_digital" in template_ids

@pytest.mark.asyncio
async def test_voice_ai_twiml_generation_and_endpoint():
    twiml = VoiceAIService.generate_switchboard_twiml(company_name="Acme Global Corporation")
    assert "<?xml version=" in twiml
    assert "<Response>" in twiml
    assert "Polly.Danielle" in twiml
    assert "Acme Global Corporation" in twiml
    assert "<Gather" in twiml

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.post("/api/v1/voice/twiml?company=Starlight%20Dynamics")
        assert res.status_code == 200
        assert "application/xml" in res.headers["content-type"]
        assert "Starlight Dynamics" in res.text

@pytest.mark.asyncio
async def test_voice_call_and_collateral_dispatch_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "sarah.vp@cloudscale.example",
            "password": "Password123!",
            "full_name": "Sarah Connor",
            "organization_name": "CloudScale Enterprises"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Ingest lead via /api/v1/crm/leads
        lead = await client.post("/api/v1/crm/leads", json={
            "company_name": "OmniCorp Logistics",
            "contact_first_name": "Marcus",
            "contact_last_name": "Vance",
            "contact_email": "marcus.vance@omnicorp.example",
            "contact_phone": "+1-555-891-2345",
            "notes": "Exploratory lead for Voice AI and Lob dispatch"
        }, headers=headers)
        assert lead.status_code == 200
        lead_id = lead.json()["id"]

        # 3. Test Voice AI Discovery Call (Simulation Mode)
        voice_res = await client.post("/api/v1/voice/call", json={
            "lead_id": lead_id,
            "target_phone": "+1-555-891-2345",
            "caller_name": "Autonomous Voice AI Dispatcher"
        }, headers=headers)
        assert voice_res.status_code == 200
        voice_data = voice_res.json()
        assert voice_data["success"] is True
        assert voice_data["mode"] == "simulated"
        assert voice_data["outcome"] == "connected"
        assert voice_data["call_sid"].startswith("CA_sim_")
        assert "OmniCorp Logistics" in voice_data["transcript"]

        # 4. Test Lob.com Postal Briefing Letter Dispatch (Simulation Mode)
        postal_res = await client.post("/api/v1/collateral/dispatch-postal", json={
            "lead_id": lead_id,
            "template_id": "executive_briefing_letter",
            "recipient_name": "Marcus Vance",
            "recipient_title": "VP of Supply Chain",
            "to_address": {
                "name": "Marcus Vance",
                "address_line1": "500 Robotics Way",
                "address_city": "Detroit",
                "address_state": "MI",
                "address_zip": "48201",
                "address_country": "US"
            }
        }, headers=headers)
        assert postal_res.status_code == 200
        postal_data = postal_res.json()
        assert postal_data["success"] is True
        assert postal_data["mode"] == "simulated"
        assert postal_data["carrier"] == "USPS"
        assert len(postal_data["tracking_number"]) == 22
        assert postal_data["tracking_number"].startswith("9400111899562")
        assert "preview_url" in postal_data

        # 5. Test SendGrid Digital Whitepaper Dispatch
        digital_res = await client.post("/api/v1/collateral/dispatch-digital", json={
            "lead_id": lead_id,
            "to_email": "marcus.vance@omnicorp.example",
            "recipient_name": "Marcus Vance"
        }, headers=headers)
        assert digital_res.status_code == 200
        digital_data = digital_res.json()
        assert digital_data["success"] is True
        assert "whitepaper_url" in digital_data

        # 6. Verify Lead Notes Updated with USPS Tracking details
        lead_check = await client.get(f"/api/v1/crm/leads/{lead_id}", headers=headers)
        assert lead_check.status_code == 200
        notes = lead_check.json().get("notes", "")
        assert "Postal Collateral Dispatched via Lob.com" in notes
        assert postal_data["tracking_number"] in notes

@pytest.mark.asyncio
async def test_dag_stage_2_executes_voice_and_postal_dispatch():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "ceo@apexenterprises.example",
            "password": "Password123!",
            "full_name": "Apex CEO",
            "organization_name": "Apex Autonomous Global"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # Run 6-bot pipeline which executes Stage 2
        dag_res = await client.post("/api/v1/pipeline/dag/execute", json={
            "company_name": "Pacific Horizon Logistics",
            "industry": "Global Container Shipping",
            "target_value": 35000.0
        }, headers=headers)
        assert dag_res.status_code == 200
        dag_data = dag_res.json()
        assert dag_data["deal_won"] is True

        # Inspect Stage 2 in timeline
        stage_2 = next(s for s in dag_data["timeline"] if s["stage"] == "discovery")
        assert stage_2["agent"] == "The Decision-Maker Pathfinder & Literature Bot"
        assert stage_2["call_outcome"] == "connected"
        assert stage_2["call_sid"].startswith("CA_sim_")
        assert stage_2["postal_tracking_number"].startswith("9400111899562")
        assert stage_2["postal_carrier"] == "USPS"
        assert stage_2["digital_whitepaper_sent"] is True

@pytest.mark.asyncio
async def test_tenant_settings_lob_api_key_masking():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "director@logistics.example",
            "password": "Password123!",
            "full_name": "Director of Growth",
            "organization_name": "Logistics Modernization Group"
        })
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Update tenant settings with Lob API key
        update_res = await client.put("/api/v1/orgs/settings", json={
            "lob_api_key": "live_lob_supersecretkey9988776655"
        }, headers=headers)
        assert update_res.status_code == 200
        data = update_res.json()
        assert data["has_lob_key"] is True
        assert data["is_lob_configured"] is True
        assert data["masked_lob_key"] is not None
        assert "••••" in data["masked_lob_key"]
        assert "live_lob_supersecretkey9988776655" not in data["masked_lob_key"]
