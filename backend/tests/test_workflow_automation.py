import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.services.workflow_engine import WorkflowEngineService

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def setup_test_tenant(client: AsyncClient):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "sarah.admin@enterpriseflow.example",
        "password": "SecurePassword123!",
        "full_name": "Sarah Flowmaster",
        "organization_name": "Enterprise Flow Automation Corp"
    })
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    org_id = reg.json()["organization_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}
    return {
        "headers": headers,
        "org_id": org_id,
        "token": token
    }

@pytest.mark.asyncio
async def test_workflow_templates_and_instantiation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ctx = await setup_test_tenant(client)
        headers = ctx["headers"]

        # 1. Fetch pre-built templates
        res = await client.get("/api/v1/workflows/templates", headers=headers)
        assert res.status_code == 200
        templates = res.json()
        assert len(templates) >= 4
        template_ids = [t["id"] for t in templates]
        assert "tpl_vip_lead_enrichment" in template_ids
        assert "tpl_critical_stockout" in template_ids
        assert "tpl_hostile_support_sla" in template_ids
        assert "tpl_post_payment_onboarding" in template_ids

        # 2. Instantiate template
        inst_res = await client.post("/api/v1/workflows/templates/tpl_vip_lead_enrichment/instantiate", headers=headers)
        assert inst_res.status_code == 200
        wf = inst_res.json()
        assert wf["trigger_type"] == "lead_created"
        assert len(wf["steps"]) >= 4
        assert "nodes" in wf["canvas_data"]
        assert len(wf["canvas_data"]["nodes"]) >= 4
        assert wf["is_active"] is True

@pytest.mark.asyncio
async def test_workflow_crud_and_canvas_persistence():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ctx = await setup_test_tenant(client)
        headers = ctx["headers"]

        # 1. Create custom workflow
        canvas = {
            "nodes": [
                {"id": "node_1", "type": "trigger", "label": "Order Placed", "action_type": "event_trigger", "x": 100, "y": 150},
                {"id": "node_2", "type": "action", "label": "Send Email", "action_type": "send_email", "x": 350, "y": 150}
            ],
            "edges": [
                {"id": "edge_1_2", "source": "node_1", "target": "node_2"}
            ]
        }
        steps = [
            {"id": "step_1", "step_type": "trigger", "action_type": "event_trigger", "config": {}},
            {"id": "step_2", "step_type": "action", "action_type": "send_email", "config": {"recipient": "client@example.com", "subject": "Order Confirmation"}}
        ]
        create_res = await client.post("/api/v1/workflows", json={
            "name": "Order Confirmation Pipeline",
            "description": "Fires on new orders",
            "trigger_type": "order_placed",
            "canvas_data": canvas,
            "steps": steps,
            "is_active": True
        }, headers=headers)
        assert create_res.status_code == 201
        created = create_res.json()
        wf_id = created["id"]
        assert created["name"] == "Order Confirmation Pipeline"
        assert len(created["steps"]) == 2

        # 2. List workflows
        list_res = await client.get("/api/v1/workflows", headers=headers)
        assert list_res.status_code == 200
        wf_list = list_res.json()
        assert len(wf_list) == 1
        assert wf_list[0]["id"] == wf_id

        # 3. Get single workflow
        get_res = await client.get(f"/api/v1/workflows/{wf_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["trigger_type"] == "order_placed"

        # 4. Update workflow
        upd_res = await client.put(f"/api/v1/workflows/{wf_id}", json={
            "name": "Updated Order Pipeline",
            "is_active": False
        }, headers=headers)
        assert upd_res.status_code == 200
        assert upd_res.json()["name"] == "Updated Order Pipeline"
        assert upd_res.json()["is_active"] is False

        # 5. Toggle active status
        toggle_res = await client.post(f"/api/v1/workflows/{wf_id}/toggle", headers=headers)
        assert toggle_res.status_code == 200
        assert toggle_res.json()["is_active"] is True

        # 6. Delete workflow
        del_res = await client.delete(f"/api/v1/workflows/{wf_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

        # Verify not found
        get_after = await client.get(f"/api/v1/workflows/{wf_id}", headers=headers)
        assert get_after.status_code == 404

@pytest.mark.asyncio
async def test_workflow_dry_run_simulation_and_branching():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ctx = await setup_test_tenant(client)
        headers = ctx["headers"]

        # Instantiate VIP lead enrichment template
        inst_res = await client.post("/api/v1/workflows/templates/tpl_vip_lead_enrichment/instantiate", headers=headers)
        assert inst_res.status_code == 200
        wf_id = inst_res.json()["id"]

        # 1. Dry run matching condition (deal value 85000 >= 10000)
        match_res = await client.post(f"/api/v1/workflows/{wf_id}/test", json={
            "trigger_payload": {
                "lead_id": "lead_999",
                "lead_name": "Titanium Aerospace",
                "estimated_value": 85000,
                "notes": "Interested in defense avionics components"
            }
        }, headers=headers)
        assert match_res.status_code == 200
        res_data = match_res.json()
        assert res_data["status"] == "completed"
        assert res_data["execution_time_ms"] >= 0
        logs = res_data["step_logs"]
        assert len(logs) == 5
        # All steps should succeed
        assert all(l["status"] == "success" for l in logs)
        # Check condition step log
        cond_log = next(l for l in logs if l["step_id"] == "step-2")
        assert cond_log["output"]["matched"] is True

        # 2. Dry run failing condition (deal value 5000 not >= 10000)
        fail_res = await client.post(f"/api/v1/workflows/{wf_id}/test", json={
            "trigger_payload": {
                "lead_id": "lead_100",
                "lead_name": "Small Tech Shop",
                "estimated_value": 5000,
                "notes": "Small prototype order"
            }
        }, headers=headers)
        assert fail_res.status_code == 200
        fail_data = fail_res.json()
        assert fail_data["status"] == "completed"
        fail_logs = fail_data["step_logs"]
        cond_fail_log = next(l for l in fail_logs if l["step_id"] == "step-2")
        assert cond_fail_log["output"]["matched"] is False
        # Downstream conditional steps should be skipped
        agent_log = next(l for l in fail_logs if l["step_id"] == "step-3")
        assert agent_log["status"] == "skipped"

@pytest.mark.asyncio
async def test_workflow_ai_agent_and_domain_actions():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ctx = await setup_test_tenant(client)
        headers = ctx["headers"]

        # Create workflow with AI agent task and domain action
        workflow_data = {
            "name": "Autonomous Deal Closer",
            "description": "Evaluates client intent and drafts response",
            "trigger_type": "inquiry_received",
            "canvas_data": {
                "nodes": [
                    {"id": "n1", "type": "trigger", "label": "Inquiry", "action_type": "event_trigger", "x": 100, "y": 100},
                    {"id": "n2", "type": "agent", "label": "AI Strategy Agent", "action_type": "ai_agent_task", "x": 300, "y": 100},
                    {"id": "n3", "type": "action", "label": "Draft PO", "action_type": "draft_po", "x": 500, "y": 100}
                ],
                "edges": [
                    {"id": "e1", "source": "n1", "target": "n2"},
                    {"id": "e2", "source": "n2", "target": "n3"}
                ]
            },
            "steps": [
                {"id": "s1", "step_type": "trigger", "action_type": "event_trigger", "config": {}},
                {
                    "id": "s2",
                    "step_type": "agent",
                    "action_type": "ai_agent_task",
                    "config": {
                        "prompt_template": "Analyze request for {client_name}: items={items}, budget={budget}. Suggest closing offer."
                    }
                },
                {
                    "id": "s3",
                    "step_type": "action",
                    "action_type": "draft_po",
                    "config": {
                        "vendor": "Acme Supplier",
                        "product_code": "PROD-9000",
                        "quantity": 100
                    }
                }
            ],
            "is_active": True
        }
        res = await client.post("/api/v1/workflows", json=workflow_data, headers=headers)
        assert res.status_code == 201
        wf_id = res.json()["id"]

        test_run = await client.post(f"/api/v1/workflows/{wf_id}/test", json={
            "trigger_payload": {
                "client_name": "MegaCorp Industries",
                "items": "50x Heavy Duty Servos",
                "budget": "$75,000"
            }
        }, headers=headers)
        assert test_run.status_code == 200
        run_data = test_run.json()
        assert run_data["status"] == "completed"
        logs = run_data["step_logs"]
        assert len(logs) == 3

        # Verify AI agent output
        agent_output = logs[1]["output"]
        assert "response" in agent_output
        assert "confidence" in agent_output

        # Verify PO draft output
        po_output = logs[2]["output"]
        assert "po_number" in po_output
        assert po_output["vendor"] == "Acme Supplier"
        assert po_output["product_code"] == "PROD-9000"

@pytest.mark.asyncio
async def test_workflow_event_dispatcher_and_execution_history():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ctx = await setup_test_tenant(client)
        headers = ctx["headers"]
        org_id = ctx["org_id"]

        # 1. Instantiate critical stockout template
        inst_res = await client.post("/api/v1/workflows/templates/tpl_critical_stockout/instantiate", headers=headers)
        assert inst_res.status_code == 200
        wf_id = inst_res.json()["id"]

        # 2. Dispatch real event trigger via WorkflowEngineService
        async with AsyncSessionLocal() as db:
            event_payload = {
                "sku": "SKU-PUMP-442",
                "product_name": "Hydraulic Pump 3000PSI",
                "current_inventory": 3,
                "reorder_point": 10,
                "stockout_risk_score": 88
            }
            results = await WorkflowEngineService.dispatch_event_triggers(
                db=db,
                org_id=org_id,
                event_type="stockout_risk_high",
                payload=event_payload
            )
            assert len(results) == 1
            execution_id = results[0].id
            assert results[0].status == "completed"
            assert results[0].execution_time_ms is not None

        # 3. Query execution runs via API
        runs_res = await client.get(f"/api/v1/workflows/{wf_id}/runs", headers=headers)
        assert runs_res.status_code == 200
        runs = runs_res.json()
        assert len(runs) >= 1
        assert runs[0]["id"] == execution_id
        assert runs[0]["status"] == "completed"

        # 4. Query single run detail
        run_detail_res = await client.get(f"/api/v1/workflows/{wf_id}/runs/{execution_id}", headers=headers)
        assert run_detail_res.status_code == 200
        run_detail = run_detail_res.json()
        assert run_detail["id"] == execution_id
        assert run_detail["workflow_id"] == wf_id
        assert len(run_detail["step_logs"]) >= 3
        # Check that PO draft was performed
        po_step = next((s for s in run_detail["step_logs"] if s.get("label") == "Generate Urgent PO" or s.get("node_type") == "action"), None)
        assert po_step is not None
        assert po_step["status"] == "success"
