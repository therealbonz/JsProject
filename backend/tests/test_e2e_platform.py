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
async def test_full_platform_e2e():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check
        health_res = await client.get("/health")
        assert health_res.status_code == 200
        assert health_res.json()["status"] == "online"

        # 2. Register Tenant A
        reg_a = await client.post("/api/v1/auth/register", json={
            "email": "admin@acmesupply.com",
            "password": "Password123!",
            "full_name": "Alice Admin",
            "organization_name": "Acme Supply Corp"
        })
        assert reg_a.status_code == 200
        token_a = reg_a.json()["access_token"]
        org_a_id = reg_a.json()["organization_id"]
        headers_a = {"Authorization": f"Bearer {token_a}", "X-Organization-Id": org_a_id}

        # 3. Register Tenant B (For Isolation Testing)
        reg_b = await client.post("/api/v1/auth/register", json={
            "email": "manager@globalcleaning.com",
            "password": "Password123!",
            "full_name": "Bob Manager",
            "organization_name": "Global Cleaning Inc"
        })
        assert reg_b.status_code == 200
        token_b = reg_b.json()["access_token"]
        org_b_id = reg_b.json()["organization_id"]
        headers_b = {"Authorization": f"Bearer {token_b}", "X-Organization-Id": org_b_id}

        # 4. Tenant A creates a Lead
        lead_payload = {
            "company_name": "Titan Freight & Warehousing",
            "company_domain": "titanfreight.com",
            "industry": "Commercial Logistics",
            "contact_first_name": "David",
            "contact_last_name": "Miller",
            "contact_email": "dmiller@titanfreight.com",
            "contact_title": "Director of Facilities"
        }
        create_lead_res = await client.post("/api/v1/crm/leads", json=lead_payload, headers=headers_a)
        assert create_lead_res.status_code == 200
        lead_a = create_lead_res.json()
        lead_a_id = lead_a["id"]
        assert lead_a["company"]["name"] == "Titan Freight & Warehousing"
        assert lead_a["pipeline_stage"] == "new"

        # 5. Multi-Tenant Security Check: Tenant B MUST NOT see Tenant A's leads
        leads_b_res = await client.get("/api/v1/crm/leads", headers=headers_b)
        assert leads_b_res.status_code == 200
        assert len(leads_b_res.json()) == 0  # Tenant B has 0 leads

        # Tenant B attempting to directly access Tenant A's lead must 404
        get_lead_b_res = await client.get(f"/api/v1/crm/leads/{lead_a_id}", headers=headers_b)
        assert get_lead_b_res.status_code == 404

        # 6. AI Agent Lead Research & Scoring (Tenant A)
        research_res = await client.post(f"/api/v1/agent/leads/{lead_a_id}/research", headers=headers_a)
        assert research_res.status_code == 200
        research_data = research_res.json()
        assert research_data["lead_score"] > 50
        assert "confidence_score" in research_data

        # Verify lead status updated in CRM
        updated_lead_res = await client.get(f"/api/v1/crm/leads/{lead_a_id}", headers=headers_a)
        assert updated_lead_res.json()["pipeline_stage"] == "ready_contact"

        # 7. AI Agent Drafts Grounded Outreach Email
        draft_res = await client.post(f"/api/v1/agent/leads/{lead_a_id}/draft-outreach", headers=headers_a)
        assert draft_res.status_code == 200
        draft_data = draft_res.json()
        assert "subject" in draft_data
        assert "body_text" in draft_data
        assert "David" in draft_data["body_text"]

        # 8. Dispatch Initial Message
        send_msg_res = await client.post(
            f"/api/v1/agent/conversations/{lead_a_id}/send-message",
            json={"subject": draft_data["subject"], "body_text": draft_data["body_text"]},
            headers=headers_a
        )
        assert send_msg_res.status_code == 200
        assert send_msg_res.json()["direction"] == "outbound"

        # 9. Test Policy Guardrail & HITL Escalation:
        # Customer requests a 20% discount (exceeds default policy max of 10%)
        sim_inbound_res = await client.post(
            f"/api/v1/agent/conversations/{lead_a_id}/inbound-simulate",
            params={"incoming_text": "We are interested, but we need a 20% discount on 100 cases to switch suppliers."},
            headers=headers_a
        )
        assert sim_inbound_res.status_code == 200
        inbound_data = sim_inbound_res.json()
        assert inbound_data["requires_hitl"] is True
        assert "20.0" in inbound_data["hitl_reason"] or "20" in inbound_data["hitl_reason"]

        # 10. Verify Human Assistance Request (HAR) is in Pending queue
        hitl_res = await client.get("/api/v1/hitl/requests?status_filter=pending", headers=headers_a)
        assert hitl_res.status_code == 200
        pending_requests = hitl_res.json()
        assert len(pending_requests) == 1
        har_id = pending_requests[0]["id"]
        assert pending_requests[0]["trigger_reason"] == "policy_discount_exceeded"

        # 11. Human Sales Manager Reviews & Resolves Request (Approve with 15% override)
        resolve_res = await client.post(
            f"/api/v1/hitl/requests/{har_id}/action",
            json={
                "action": "approve",
                "instructions": "Approved custom 15% tier for bulk volume",
                "custom_reply": "We spoke with our regional sales director and approved a 15% volume discount for your 100-case order."
            },
            headers=headers_a
        )
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "approved"

        # 12. Verify Audit Logs
        audit_res = await client.get("/api/v1/hitl/audit-logs", headers=headers_a)
        assert audit_res.status_code == 200
        actions = [log["action"] for log in audit_res.json()]
        assert "lead_researched_and_scored" in actions
        assert "hitl_request_created" in actions
        assert "hitl_approve" in actions
