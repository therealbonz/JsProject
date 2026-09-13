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
async def test_pipeline_dag_template_registration():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for prefix in ["/api/v1/pipeline/dag/template", "/JsProject/api/v1/pipeline/dag/template"]:
            res = await client.get(prefix)
            assert res.status_code == 200
            data = res.json()
            assert "template" in data
            assert "stages" in data

            template = data["template"]
            assert template["id"] == "tpl_autonomous_6bot_pipeline"
            assert "6-Stage Autonomous AI Sales Pipeline DAG" in template["name"]

            # Verify 6 nodes in DAG
            nodes = template["canvas_data"]["nodes"]
            assert len(nodes) == 6
            stage_ids = [n["config"]["stage"] for n in nodes]
            assert "lead_dev" in stage_ids
            assert "discovery" in stage_ids
            assert "sdr" in stage_ids
            assert "setter" in stage_ids
            assert "exec_closer" in stage_ids
            assert "closer" in stage_ids

            # Verify 5 connecting DAG handoff edges
            edges = template["canvas_data"]["edges"]
            assert len(edges) == 5

@pytest.mark.asyncio
async def test_step_by_step_dag_advancement():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "pipeline.admin@enterprisesaas.example",
            "password": "Password123!",
            "full_name": "Pipeline Lead",
            "organization_name": "Enterprise SaaS Dynamics"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Ingest initial raw prospect
        lead_res = await client.post("/api/v1/crm/leads", headers=headers, json={
            "company_name": "Target Corp Industries",
            "contact_first_name": "Initial",
            "contact_last_name": "Inbound",
            "contact_email": "contact@targetcorp.example",
            "notes": "Raw web lead from marketing site."
        })
        assert lead_res.status_code == 200
        lead_id = lead_res.json()["id"]

        # Step 1: Run Stage 1 (The Lead Developer)
        step1 = await client.post("/api/v1/pipeline/dag/step", headers=headers, json={"lead_id": lead_id})
        assert step1.status_code == 200
        s1_data = step1.json()
        assert s1_data["stage_advanced"] == "lead_dev"
        assert s1_data["telemetry"]["lead_score"] == 94
        assert s1_data["telemetry"]["pipeline_stage"] == "researching"

        # Step 2: Run Stage 2 (Decision-Maker Pathfinder & Literature Bot)
        step2 = await client.post("/api/v1/pipeline/dag/step", headers=headers, json={"lead_id": lead_id})
        assert step2.status_code == 200
        s2_data = step2.json()
        assert s2_data["stage_advanced"] == "discovery"
        assert s2_data["telemetry"]["call_outcome"] == "connected"
        assert len(s2_data["telemetry"]["literature_dispatched"]) >= 2
        assert s2_data["telemetry"]["pipeline_stage"] == "connected"

        # Step 3: Run Stage 3 (Cold Outreach SDR)
        step3 = await client.post("/api/v1/pipeline/dag/step", headers=headers, json={"lead_id": lead_id})
        assert step3.status_code == 200
        s3_data = step3.json()
        assert s3_data["stage_advanced"] == "sdr"
        assert "touchpoint_1_email" in s3_data["telemetry"]["outbound_sequence"]
        assert s3_data["telemetry"]["pipeline_stage"] == "contacted"

        # Step 4: Run Stage 4 (Appointment Setter)
        step4 = await client.post("/api/v1/pipeline/dag/step", headers=headers, json={"lead_id": lead_id})
        assert step4.status_code == 200
        s4_data = step4.json()
        assert s4_data["stage_advanced"] == "setter"
        assert s4_data["telemetry"]["appointment_id"] is not None
        assert s4_data["telemetry"]["pipeline_stage"] == "qualified"

        # Step 5: Run Stage 5 (Executive Sales Bot)
        step5 = await client.post("/api/v1/pipeline/dag/step", headers=headers, json={"lead_id": lead_id})
        assert step5.status_code == 200
        s5_data = step5.json()
        assert s5_data["stage_advanced"] == "exec_closer"
        assert s5_data["telemetry"]["proposal_value"] == 25000.0
        assert s5_data["telemetry"]["pipeline_stage"] == "proposal"

        # Step 6: Run Stage 6 (Objection Closer & Expansion)
        step6 = await client.post("/api/v1/pipeline/dag/step", headers=headers, json={"lead_id": lead_id})
        assert step6.status_code == 200
        s6_data = step6.json()
        assert s6_data["stage_advanced"] == "closer"
        assert s6_data["telemetry"]["deal_status"] == "won"
        assert s6_data["telemetry"]["pipeline_stage"] == "won"

        # Step 7: Subsequent step signals already won
        step7 = await client.post("/api/v1/pipeline/dag/step", headers=headers, json={"lead_id": lead_id})
        assert step7.status_code == 200
        assert step7.json()["already_won"] is True

@pytest.mark.asyncio
async def test_full_autonomous_dag_execution():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "cro@hyperautomation.example",
            "password": "Password123!",
            "full_name": "Chief Revenue Officer",
            "organization_name": "HyperScale Operations"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Run full autonomous 6-bot pipeline execution
        res = await client.post("/api/v1/pipeline/dag/execute", headers=headers, json={
            "company_name": "Titanium Logistics Cloud",
            "industry": "Enterprise Supply Chain & Logistics",
            "target_value": 45000.0
        })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["deal_won"] is True
        assert data["final_stage"] == "won"
        assert data["total_stages_executed"] == 6
        assert len(data["timeline"]) == 6

        # Verify stages in timeline
        stages = [t["stage"] for t in data["timeline"]]
        assert stages == ["lead_dev", "discovery", "sdr", "setter", "exec_closer", "closer"]

        # Verify Stage 2 literature dispatch is tracked
        t2 = data["timeline"][1]
        assert "Autonomous B2B Architecture Blueprint" in t2["literature_dispatched"][0]

        # Verify Stage 4 appointment was locked
        t4 = data["timeline"][3]
        assert t4["appointment_id"] is not None

        # Verify Stage 5 proposal generated
        t5 = data["timeline"][4]
        assert t5["proposal_value"] == 25000.0

@pytest.mark.asyncio
async def test_pipeline_status_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "vp@datanetics.example",
            "password": "Password123!",
            "full_name": "VP Growth",
            "organization_name": "Datanetics Cloud"
        })
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Run full pipeline
        exec_res = await client.post("/api/v1/pipeline/dag/execute", headers=headers, json={
            "company_name": "Zenith AI Corp",
            "target_value": 25000.0
        })
        lead_id = exec_res.json()["lead_id"]

        # Retrieve status
        status_res = await client.get(f"/api/v1/pipeline/dag/status/{lead_id}", headers=headers)
        assert status_res.status_code == 200
        st = status_res.json()
        assert st["lead_id"] == lead_id
        assert st["pipeline_stage"] == "won"
        assert st["status"] == "converted"
        assert len(st["appointments"]) >= 1
        assert len(st["call_logs"]) >= 1
        assert len(st["opportunities"]) >= 1
        assert st["opportunities"][0]["stage"] == "won"
        assert len(st["stages_roster"]) == 6
