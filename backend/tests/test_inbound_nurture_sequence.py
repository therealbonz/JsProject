import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base
from app.services.nurture_sequence_service import NurtureSequenceService

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_cadence_definitions_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        res = await client.get("/api/v1/nurture/cadence-definitions")
        assert res.status_code == 200
        data = res.json()
        assert "steps" in data
        steps = data["steps"]
        assert len(steps) == 5

        # Check step 1 through 5 structure
        assert steps[0]["step"] == 1
        assert "Welcome" in steps[0]["name"]
        assert steps[1]["step"] == 2
        assert "SMS" in steps[1]["name"]
        assert steps[2]["step"] == 3
        assert "SDR" in steps[2]["name"]
        assert steps[3]["step"] == 4
        assert "Voice" in steps[3]["name"] or "Postal" in steps[3]["name"]
        assert steps[4]["step"] == 5
        assert "Executive" in steps[4]["name"]

@pytest.mark.asyncio
async def test_inbound_lead_capture_and_auto_enrollment():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register organization
        reg = await client.post("/api/v1/auth/register", json={
            "email": "director@vortexcloud.example",
            "password": "Password123!",
            "full_name": "David Miller",
            "organization_name": "Vortex Cloud Systems"
        })
        assert reg.status_code == 200
        org_id = reg.json()["organization_id"]
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Ingest inbound lead via /api/v1/nurture/inbound-capture
        res = await client.post("/api/v1/nurture/inbound-capture", json={
            "name": "Elena Rostova",
            "email": "elena.rostova@quantumlogistics.example",
            "company_name": "Quantum Logistics Global",
            "phone": "+1 (555) 432-8765",
            "industry": "Supply Chain & Freight",
            "source": "landing_page_whitepaper_form",
            "custom_notes": "Downloaded 16-page Autonomous Workforce ROI dossier.",
            "org_id": org_id
        })
        assert res.status_code == 200
        data = res.json()
        assert data["enrolled"] is True
        assert data["nurture_status"] == "active"
        assert data["nurture_step"] == 1
        lead_id = data["lead_id"]
        assert lead_id is not None

        # Verify Step 1 touchpoint executed and logged
        history = data["history"]
        assert len(history) == 1
        assert history[0]["step"] == 1
        assert "Instant Welcome" in history[0]["name"]
        assert history[0]["channel"] == "email"

        # 3. Retrieve lead status via /api/v1/nurture/lead/{lead_id}
        status_res = await client.get(f"/api/v1/nurture/lead/{lead_id}", headers=headers)
        assert status_res.status_code == 200
        lead_status = status_res.json()
        assert lead_status["nurture_status"] == "active"
        assert lead_status["nurture_step"] == 1
        assert len(lead_status["nurture_history"]) == 1

@pytest.mark.asyncio
async def test_step_by_step_cadence_advancement_across_5_touchpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "admin@aeropulse.example",
            "password": "Password123!",
            "full_name": "Marcus Kane",
            "organization_name": "AeroPulse Aviation"
        })
        assert reg.status_code == 200
        org_id = reg.json()["organization_id"]
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # Ingest inbound lead (starts at Step 1)
        cap = await client.post("/api/v1/nurture/inbound-capture", json={
            "name": "Sarah Connor",
            "email": "sarah.connor@cyberdyne.example",
            "company_name": "Cyberdyne Systems",
            "phone": "+1 (555) 789-0123",
            "org_id": org_id
        })
        lead_id = cap.json()["lead_id"]

        # Step 1 was executed on ingest. Advance to Step 2 (SMS)
        adv2 = await client.post("/api/v1/nurture/advance", json={
            "lead_id": lead_id,
            "force": True
        }, headers=headers)
        assert adv2.status_code == 200
        d2 = adv2.json()
        assert d2["success"] is True
        assert d2["executed_step"] == 2
        assert d2["next_step"] == 3
        assert d2["nurture_status"] == "active"

        # Advance to Step 3 (SDR 1-to-1 Email)
        adv3 = await client.post("/api/v1/nurture/advance", json={
            "lead_id": lead_id,
            "force": True
        }, headers=headers)
        assert adv3.status_code == 200
        d3 = adv3.json()
        assert d3["executed_step"] == 3
        assert d3["next_step"] == 4

        # Advance to Step 4 (Twilio Voice AI / Lob Postcard)
        adv4 = await client.post("/api/v1/nurture/advance", json={
            "lead_id": lead_id,
            "force": True
        }, headers=headers)
        assert adv4.status_code == 200
        d4 = adv4.json()
        assert d4["executed_step"] == 4
        assert d4["next_step"] == 5

        # Advance to Step 5 (Senior Executive Sales Bot Close)
        adv5 = await client.post("/api/v1/nurture/advance", json={
            "lead_id": lead_id,
            "force": True
        }, headers=headers)
        assert adv5.status_code == 200
        d5 = adv5.json()
        assert d5["executed_step"] == 5
        assert d5["cadence_completed"] is True
        assert d5["nurture_status"] == "completed_cadence"

        # Verify all 5 touchpoints are saved in lead history
        st = await client.get(f"/api/v1/nurture/lead/{lead_id}", headers=headers)
        hist = st.json()["nurture_history"]
        assert len(hist) == 5
        step_numbers = [h["step"] for h in hist]
        assert step_numbers == [1, 2, 3, 4, 5]

@pytest.mark.asyncio
async def test_auto_pause_on_prospect_reply_and_meeting_booking():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "ops@solardrive.example",
            "password": "Password123!",
            "full_name": "Rachel Zane",
            "organization_name": "SolarDrive Logistics"
        })
        org_id = reg.json()["organization_id"]
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        cap = await client.post("/api/v1/nurture/inbound-capture", json={
            "name": "Harvey Specter",
            "email": "harvey.specter@pearson.example",
            "company_name": "Pearson Hardman",
            "org_id": org_id
        })
        lead_id = cap.json()["lead_id"]

        # Prospect replies: pause cadence
        pause_res = await client.post(f"/api/v1/nurture/pause/{lead_id}", json={
            "event": "replied",
            "notes": "Harvey replied asking for custom SLA options."
        }, headers=headers)
        assert pause_res.status_code == 200
        p_data = pause_res.json()
        assert p_data["new_status"] == "paused_replied"

        # Attempting to advance paused lead should not execute touchpoint
        adv = await client.post("/api/v1/nurture/advance", json={
            "lead_id": lead_id,
            "force": False
        }, headers=headers)
        assert adv.status_code == 200
        assert adv.json()["executed"] is False
        assert "paused" in adv.json()["reason"]

        # Resume cadence
        resume_res = await client.post(f"/api/v1/nurture/resume/{lead_id}", headers=headers)
        assert resume_res.status_code == 200
        assert resume_res.json()["nurture_status"] == "active"

        # Prospect books a meeting: pause and mark completed_booked
        book_res = await client.post(f"/api/v1/nurture/pause/{lead_id}", json={
            "event": "booked_demo",
            "notes": "Demo confirmed for Thursday 2 PM."
        }, headers=headers)
        assert book_res.status_code == 200
        assert book_res.json()["new_status"] == "completed_booked"

@pytest.mark.asyncio
async def test_cadence_telemetry_aggregation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "analytics@telemetryhub.example",
            "password": "Password123!",
            "full_name": "Alan Turing",
            "organization_name": "Telemetry Hub Inc"
        })
        org_id = reg.json()["organization_id"]
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # Ingest 3 leads
        l1 = await client.post("/api/v1/nurture/inbound-capture", json={
            "name": "Lead One",
            "email": "one@example.com",
            "org_id": org_id
        })
        l2 = await client.post("/api/v1/nurture/inbound-capture", json={
            "name": "Lead Two",
            "email": "two@example.com",
            "org_id": org_id
        })
        l3 = await client.post("/api/v1/nurture/inbound-capture", json={
            "name": "Lead Three",
            "email": "three@example.com",
            "org_id": org_id
        })

        # Advance Lead 2 to step 2
        await client.post("/api/v1/nurture/advance", json={
            "lead_id": l2.json()["lead_id"],
            "force": True
        }, headers=headers)

        # Mark Lead 3 as booked demo
        await client.post(f"/api/v1/nurture/pause/{l3.json()['lead_id']}", json={
            "event": "booked_demo"
        }, headers=headers)

        # Query organization telemetry
        tel_res = await client.get("/api/v1/nurture/telemetry", headers=headers)
        assert tel_res.status_code == 200
        metrics = tel_res.json()

        assert metrics["total_enrolled"] == 3
        assert metrics["active_in_cadence"] == 2  # l1 and l2
        assert metrics["converted_demos_booked"] == 1  # l3
        assert metrics["demo_conversion_rate_pct"] == 33.3
        assert metrics["step_breakdown"]["1"] >= 1
        assert metrics["step_breakdown"]["2"] >= 1
