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

        # 13. Comprehensive Quick Add with Notes & Call Tracking (when last call was & what was said)
        comprehensive_lead_payload = {
            "company_name": "Apex Cold Storage & Supply",
            "company_domain": "apexcold.com",
            "industry": "Cold Storage Logistics",
            "contact_first_name": "Elena",
            "contact_last_name": "Rostova",
            "contact_email": "erostova@apexcold.com",
            "contact_title": "VP of Operations",
            "notes": "Operates 4 temperature-controlled facilities. Evaluating sub-zero degreaser suppliers.",
            "last_call_at": "2026-09-08T14:30:00Z",
            "last_call_outcome": "connected",
            "last_call_notes": "Spoke with Elena for 15 minutes. Discussed bulk disinfectant pricing and delivery cadence. Requested sample batch and formal pricing quote.",
            "call_duration_minutes": 15
        }
        create_comp_res = await client.post("/api/v1/crm/leads", json=comprehensive_lead_payload, headers=headers_a)
        assert create_comp_res.status_code == 200
        comp_lead = create_comp_res.json()
        comp_lead_id = comp_lead["id"]

        # Assert notes & last call details are tracked on the lead
        assert comp_lead["notes"] == "Operates 4 temperature-controlled facilities. Evaluating sub-zero degreaser suppliers."
        assert comp_lead["last_call_at"] is not None
        assert "Spoke with Elena" in comp_lead["last_call_notes"]
        assert comp_lead["last_call_outcome"] == "connected"
        assert comp_lead["pipeline_stage"] == "connected"

        # Assert CallLog was automatically created
        assert len(comp_lead["call_logs"]) == 1
        initial_call = comp_lead["call_logs"][0]
        assert initial_call["outcome"] == "connected"
        assert initial_call["duration_minutes"] == 15
        assert "Spoke with Elena" in initial_call["notes"]

        # 14. Log a Follow-up Call for this Account
        followup_call_payload = {
            "outcome": "scheduled_demo",
            "duration_minutes": 20,
            "notes": "Second call with Elena and facility manager. Reviewed bulk catalog discounts. Scheduled on-site trial demo for next Thursday.",
            "next_steps": "Send calendar invite and prepare chemical compatibility spec sheet."
        }
        followup_res = await client.post(f"/api/v1/crm/leads/{comp_lead_id}/calls", json=followup_call_payload, headers=headers_a)
        assert followup_res.status_code == 200
        call_entry = followup_res.json()
        assert call_entry["outcome"] == "scheduled_demo"
        assert "Scheduled on-site trial demo" in call_entry["notes"]

        # Verify calls list endpoint returns both calls in chronological order
        calls_list_res = await client.get(f"/api/v1/crm/leads/{comp_lead_id}/calls", headers=headers_a)
        assert calls_list_res.status_code == 200
        all_calls = calls_list_res.json()
        assert len(all_calls) == 2
        assert all_calls[0]["outcome"] == "scheduled_demo"  # Most recent first
        assert all_calls[1]["outcome"] == "connected"

        # 15. Verify updating Account Notes via PATCH
        patch_res = await client.patch(f"/api/v1/crm/leads/{comp_lead_id}", json={
            "notes": "Updated: Elena approved demo trial. Primary decision maker is confirmed."
        }, headers=headers_a)
        assert patch_res.status_code == 200
        assert "Elena approved demo trial" in patch_res.json()["notes"]

        # 16. Multi-Tenant Isolation Check for Call Tracking: Tenant B cannot see Tenant A's call logs
        calls_tenant_b = await client.get(f"/api/v1/crm/leads/{comp_lead_id}/calls", headers=headers_b)
        assert calls_tenant_b.status_code == 404

@pytest.mark.asyncio
async def test_quick_add_notes_and_call_tracking():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register organization
        reg = await client.post("/api/v1/auth/register", json={
            "email": "rep@omnisupply.com",
            "password": "Password123!",
            "full_name": "Jordan Rep",
            "organization_name": "Omni Supply Ltd"
        })
        assert reg.status_code == 200
        headers = {
            "Authorization": f"Bearer {reg.json()['access_token']}",
            "X-Organization-Id": reg.json()["organization_id"]
        }

        # Case 1: Quick Add with notes only (no call yet)
        lead_no_call = {
            "company_name": "Blue Horizon Logistics",
            "industry": "Maritime Shipping",
            "contact_first_name": "Carl",
            "contact_last_name": "Schmidt",
            "contact_email": "cschmidt@bluehorizon.com",
            "notes": "Large fleet requiring monthly degreaser resupply."
        }
        res1 = await client.post("/api/v1/crm/leads", json=lead_no_call, headers=headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["notes"] == "Large fleet requiring monthly degreaser resupply."
        assert data1["last_call_at"] is None
        assert data1["last_call_notes"] is None
        assert len(data1["call_logs"]) == 0
        lead1_id = data1["id"]

        # Case 2: Log a call after the fact for Case 1
        log_res = await client.post(f"/api/v1/crm/leads/{lead1_id}/calls", json={
            "caller_name": "Jordan Rep",
            "outcome": "left_voicemail",
            "duration_minutes": 2,
            "notes": "Left voicemail with Carl Schmidt introducing our industrial catalog.",
            "next_steps": "Call again in 2 business days"
        }, headers=headers)
        assert log_res.status_code == 200
        call_entry = log_res.json()
        assert call_entry["outcome"] == "left_voicemail"
        assert call_entry["duration_minutes"] == 2
        assert "Left voicemail with Carl" in call_entry["notes"]
        assert call_entry["caller_name"] == "Jordan Rep"

        # Check lead now reflects last call
        refreshed_lead = await client.get(f"/api/v1/crm/leads/{lead1_id}", headers=headers)
        assert refreshed_lead.json()["last_call_at"] is not None
        assert refreshed_lead.json()["last_call_outcome"] == "left_voicemail"
        assert len(refreshed_lead.json()["call_logs"]) == 1

        # Case 3: 404 for non-existent lead
        err_res = await client.post("/api/v1/crm/leads/non-existent-lead-id/calls", json={
            "outcome": "connected",
            "notes": "Test"
        }, headers=headers)
        assert err_res.status_code == 404

@pytest.mark.asyncio
async def test_client_sales_crm_and_lead_conversion():
    """
    Verify CRM 2: Client Accounts, Sales Ledger, Revenue Tracking, and Won-Lead Conversion Bridge.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Setup Tenant Org
        reg = await client.post("/api/v1/auth/register", json={
            "email": "director@vanguard.com",
            "password": "Password123!",
            "full_name": "Marcus Vance",
            "organization_name": "Vanguard Enterprises"
        })
        assert reg.status_code == 200
        headers = {
            "Authorization": f"Bearer {reg.json()['access_token']}",
            "X-Organization-Id": reg.json()["organization_id"]
        }

        # 2. Quick Add Client Account directly in CRM 2
        client_payload = {
            "account_name": "Titan Industrial Supply",
            "company_domain": "titanindustrial.com",
            "industry": "Heavy Manufacturing",
            "contact_first_name": "Rachel",
            "contact_last_name": "Chen",
            "contact_email": "rchen@titanindustrial.com",
            "contact_phone": "+1 (555) 234-5678",
            "account_tier": "enterprise",
            "reorder_cadence_days": 45,
            "notes": "Net 30 terms. Requires palletized delivery at Dock 4."
        }
        res_create = await client.post("/api/v1/crm/clients", json=client_payload, headers=headers)
        assert res_create.status_code == 200
        client_data = res_create.json()
        client_id = client_data["id"]
        assert client_data["account_name"] == "Titan Industrial Supply"
        assert client_data["account_tier"] == "enterprise"
        assert client_data["total_revenue"] == 0.0
        assert client_data["order_count"] == 0
        assert client_data["reorder_cadence_days"] == 45
        assert client_data["next_reorder_date"] is not None

        # 3. Log First Sale for Client
        sale1_payload = {
            "amount": 4500.00,
            "status": "completed",
            "payment_method": "credit_terms_30",
            "items_summary": "50x Industrial Degreaser Drums, 10x Chemical Pumps",
            "sales_rep_name": "Marcus Vance",
            "notes": "PO-99102 billed under Master Services Agreement"
        }
        res_sale1 = await client.post(f"/api/v1/crm/clients/{client_id}/sales", json=sale1_payload, headers=headers)
        assert res_sale1.status_code == 200
        sale1 = res_sale1.json()
        assert sale1["amount"] == 4500.00
        assert sale1["order_number"].startswith("SO-")
        assert sale1["status"] == "completed"

        # 4. Log Second Sale for Client
        sale2_payload = {
            "amount": 2500.00,
            "order_number": "SO-CUSTOM-002",
            "status": "completed",
            "payment_method": "wire_transfer",
            "items_summary": "25x Replacement Filter Cartridges",
            "sales_rep_name": "Marcus Vance",
            "notes": "Rush delivery requested"
        }
        res_sale2 = await client.post(f"/api/v1/crm/clients/{client_id}/sales", json=sale2_payload, headers=headers)
        assert res_sale2.status_code == 200
        sale2 = res_sale2.json()
        assert sale2["order_number"] == "SO-CUSTOM-002"
        assert sale2["amount"] == 2500.00

        # 5. Check Client Account reflection (total revenue & order count updated)
        res_get_client = await client.get(f"/api/v1/crm/clients/{client_id}", headers=headers)
        assert res_get_client.status_code == 200
        updated_client = res_get_client.json()
        assert updated_client["total_revenue"] == 7000.00
        assert updated_client["order_count"] == 2

        # 6. Check Sales Ledger listing
        res_sales_list = await client.get(f"/api/v1/crm/clients/{client_id}/sales", headers=headers)
        assert res_sales_list.status_code == 200
        sales_list = res_sales_list.json()
        assert len(sales_list) == 2

        # 7. Check CRM 2 KPI Overview
        res_stats = await client.get("/api/v1/crm/clients/stats/overview", headers=headers)
        assert res_stats.status_code == 200
        stats = res_stats.json()
        assert stats["total_revenue"] == 7000.00
        assert stats["active_clients_count"] == 1
        assert stats["total_orders_count"] == 2
        assert stats["average_order_value"] == 3500.00

        # 8. Update Client Notes & Tier
        res_patch = await client.patch(f"/api/v1/crm/clients/{client_id}", json={
            "account_tier": "vip",
            "notes": "Upgraded to VIP pricing tier with 5% quarterly rebate."
        }, headers=headers)
        assert res_patch.status_code == 200
        assert res_patch.json()["account_tier"] == "vip"
        assert "VIP pricing tier" in res_patch.json()["notes"]

        # 9. Test Lead-to-Client Conversion Bridge from CRM 1
        # Create a prospect lead in CRM 1
        lead_res = await client.post("/api/v1/crm/leads", json={
            "company_name": "Apex Logistics Group",
            "company_domain": "apexlogistics.com",
            "industry": "Third-Party Logistics",
            "contact_first_name": "David",
            "contact_last_name": "Kim",
            "contact_email": "dkim@apexlogistics.com",
            "notes": "Hot lead negotiating annual janitorial and maintenance contract."
        }, headers=headers)
        assert lead_res.status_code == 200
        lead_id = lead_res.json()["id"]

        # Convert Won Lead to Active Client in CRM 2 with an initial order
        conversion_payload = {
            "account_tier": "premium",
            "reorder_cadence_days": 30,
            "initial_order_amount": 12000.00,
            "initial_order_items": "Annual Warehouse Disinfection Contract - Q1 Batch",
            "notes": "Converted from outbound campaign. Key decision maker David Kim."
        }
        conv_res = await client.post(f"/api/v1/crm/leads/{lead_id}/convert-to-client", json=conversion_payload, headers=headers)
        assert conv_res.status_code == 200
        converted_client = conv_res.json()
        assert converted_client["account_name"] == "Apex Logistics Group"
        assert converted_client["account_tier"] == "premium"
        assert converted_client["total_revenue"] == 12000.00
        assert converted_client["order_count"] == 1
        assert len(converted_client["sales"]) == 1
        assert converted_client["sales"][0]["amount"] == 12000.00

        # Verify Lead pipeline stage in CRM 1 is now "won"
        check_lead = await client.get(f"/api/v1/crm/leads/{lead_id}", headers=headers)
        assert check_lead.json()["pipeline_stage"] == "won"

        # Check Updated KPI Overview across both accounts
        res_stats_after = await client.get("/api/v1/crm/clients/stats/overview", headers=headers)
        assert res_stats_after.status_code == 200
        stats_after = res_stats_after.json()
        assert stats_after["total_revenue"] == 19000.00  # 7000 + 12000
        assert stats_after["active_clients_count"] == 2
        assert stats_after["total_orders_count"] == 3
        assert stats_after["average_order_value"] == round(19000.00 / 3, 2)

        # 10. Multi-Tenant Isolation
        reg_other = await client.post("/api/v1/auth/register", json={
            "email": "other@competitor.com",
            "password": "Password123!",
            "full_name": "Eve Spy",
            "organization_name": "Competitor Org"
        })
        other_headers = {
            "Authorization": f"Bearer {reg_other.json()['access_token']}",
            "X-Organization-Id": reg_other.json()["organization_id"]
        }
        # Competitor sees 0 clients and 0 sales
        other_clients = await client.get("/api/v1/crm/clients", headers=other_headers)
        assert len(other_clients.json()) == 0
        other_stats = await client.get("/api/v1/crm/clients/stats/overview", headers=other_headers)
        assert other_stats.json()["total_revenue"] == 0.0
        # Competitor cannot access Vanguard's client
        err_access = await client.get(f"/api/v1/crm/clients/{client_id}", headers=other_headers)
        assert err_access.status_code == 404


