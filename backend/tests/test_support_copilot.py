import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.crm import ClientAccount, ClientSale, SaaSLicense, Company
from app.models.conversation import Conversation, Message
from app.models.hitl import HumanAssistanceRequest

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

async def setup_test_tenant_and_client(client: AsyncClient):
    # 1. Register test tenant
    reg = await client.post("/api/v1/auth/register", json={
        "email": "sarah.rep@apexsupply.example",
        "password": "SecurePassword123!",
        "full_name": "Sarah Jenkins",
        "organization_name": "Apex Industrial Supply"
    })
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    org_id = reg.json()["organization_id"]
    headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

    # 2. Create client account
    c_res = await client.post("/api/v1/crm/clients", json={
        "account_name": "Pacific Cascade Lumber",
        "contact_first_name": "Marcus",
        "contact_last_name": "Vance",
        "contact_email": "marcus@pacificcascade.example",
        "contact_phone": "+1 (555) 432-8899",
        "reorder_cadence_days": 30,
        "status": "active"
    }, headers=headers)
    assert c_res.status_code == 200
    client_id = c_res.json()["id"]

    # Generate portal link
    link_res = await client.post(f"/api/v1/crm/clients/{client_id}/portal-link", headers=headers)
    assert link_res.status_code == 200
    portal_token = link_res.json()["portal_access_token"]

    return {
        "headers": headers,
        "org_id": org_id,
        "token": token,
        "client_id": client_id,
        "portal_token": portal_token
    }

@pytest.mark.asyncio
async def test_portal_copilot_order_lookup_and_history():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ctx = await setup_test_tenant_and_client(client)
        portal_token = ctx["portal_token"]
        client_id = ctx["client_id"]

        # Create a sale record for the client
        async with AsyncSessionLocal() as db:
            sale = ClientSale(
                id="sale-copilot-001",
                organization_id=ctx["org_id"],
                client_id=client_id,
                order_number="ORD-7788",
                amount=14500.00,
                sale_date=datetime.now(timezone.utc),
                status="shipped",
                payment_status="paid",
                items_summary="50x Kiln-Dried Pine Beams, 100x Structural Brackets"
            )
            db.add(sale)
            await db.commit()

        # 1. Customer asks about order status
        chat_res = await client.post(
            f"/api/v1/support-copilot/portal/{portal_token}/chat",
            json={"message": "Can you check on my order ORD-7788 status and tracking?"}
        )
        assert chat_res.status_code == 200
        data = chat_res.json()
        assert "ORD-7788" in data["reply"]
        assert "SHIPPED" in data["reply"]
        assert any(t["tool_name"] == "lookup_order_status" for t in data["tool_calls"])
        assert data["sentiment"] in ["neutral", "positive"]

        # 2. Customer asks for recent orders
        chat_res2 = await client.post(
            f"/api/v1/support-copilot/portal/{portal_token}/chat",
            json={"message": "Show me my recent orders"}
        )
        assert chat_res2.status_code == 200
        data2 = chat_res2.json()
        assert "ORD-7788" in data2["reply"]
        assert any(t["tool_name"] == "get_recent_orders" for t in data2["tool_calls"])

        # 3. Retrieve chat history
        history_res = await client.get(f"/api/v1/support-copilot/portal/{portal_token}/history")
        assert history_res.status_code == 200
        messages = history_res.json()
        assert len(messages) >= 4  # 2 customer messages + 2 copilot responses
        assert messages[0]["direction"] == "inbound"
        assert messages[1]["direction"] == "outbound"
        assert messages[1]["sender_type"] in ["ai_agent", "ai_copilot"]

@pytest.mark.asyncio
async def test_portal_copilot_restock_forecast_and_snooze():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ctx = await setup_test_tenant_and_client(client)
        portal_token = ctx["portal_token"]
        client_id = ctx["client_id"]

        # Update client account with restock schedule
        async with AsyncSessionLocal() as db:
            cl = (await db.execute(select(ClientAccount).where(ClientAccount.id == client_id))).scalar_one()
            cl.next_reorder_date = datetime.now(timezone.utc) + timedelta(days=12)
            cl.reorder_cadence_days = 28
            await db.commit()

        # 1. Query restock schedule
        res1 = await client.post(
            f"/api/v1/support-copilot/portal/{portal_token}/chat",
            json={"message": "What is our replenishment restock forecast and next scheduled order?"}
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert any(t["tool_name"] == "check_restock_forecast" for t in data1["tool_calls"])
        assert "Replenishment" in data1["reply"]

        # 2. Snooze restock schedule
        res2 = await client.post(
            f"/api/v1/support-copilot/portal/{portal_token}/chat",
            json={"message": "Please snooze our upcoming restock delivery by 14 days"}
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert any(t["tool_name"] == "snooze_restock_schedule" for t in data2["tool_calls"])
        assert "snoozed" in data2["reply"].lower() or "updated" in data2["reply"].lower()

        # Verify database updated
        async with AsyncSessionLocal() as db:
            cl_updated = (await db.execute(select(ClientAccount).where(ClientAccount.id == client_id))).scalar_one()
            assert cl_updated.next_reorder_date.date() > (datetime.now(timezone.utc) + timedelta(days=20)).date()

        # 3. Accelerate restock schedule
        res3 = await client.post(
            f"/api/v1/support-copilot/portal/{portal_token}/chat",
            json={"message": "We have an emergency project, we need stock immediately, ship now!"}
        )
        assert res3.status_code == 200
        data3 = res3.json()
        assert any(t["tool_name"] == "accelerate_restock_schedule" for t in data3["tool_calls"])
        assert "accelerated" in data3["reply"].lower() or "priority" in data3["reply"].lower()

@pytest.mark.asyncio
async def test_portal_copilot_billing_and_licenses():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ctx = await setup_test_tenant_and_client(client)
        portal_token = ctx["portal_token"]
        client_id = ctx["client_id"]

        # Set billing info & add SaaSLicense
        async with AsyncSessionLocal() as db:
            comp = Company(
                id="comp-support-001",
                organization_id=ctx["org_id"],
                name="Pacific Cascade Lumber"
            )
            db.add(comp)
            await db.flush()

            cl = (await db.execute(select(ClientAccount).where(ClientAccount.id == client_id))).scalar_one()
            cl.company_id = comp.id
            cl.has_payment_method_on_file = True
            cl.card_last4 = "8812"
            cl.card_brand = "mastercard"
            cl.auto_charge_enabled = True
            cl.account_tier = "enterprise"

            now_utc = datetime.now(timezone.utc)
            lic = SaaSLicense(
                id="lic-support-001",
                organization_id=ctx["org_id"],
                client_id=client_id,
                company_id=comp.id,
                license_key="LIC-APEX-ENT-8812",
                product_name="Enterprise AI Platform",
                plan_tier="Enterprise Pro",
                license_status="active",
                billing_interval="monthly",
                contract_start_date=now_utc,
                renewal_date=now_utc + timedelta(days=365)
            )
            db.add(lic)
            await db.commit()

        # Ask copilot about billing and payment method
        res = await client.post(
            f"/api/v1/support-copilot/portal/{portal_token}/chat",
            json={"message": "Can you check my billing status, active licenses, and card on file?"}
        )
        assert res.status_code == 200
        data = res.json()
        assert any(t["tool_name"] == "check_billing_status" for t in data["tool_calls"])
        assert "8812" in data["reply"]
        assert "ENTERPRISE PRO" in data["reply"].upper()

@pytest.mark.asyncio
async def test_sentiment_and_explicit_hitl_escalation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ctx = await setup_test_tenant_and_client(client)
        portal_token = ctx["portal_token"]
        client_id = ctx["client_id"]

        # 1. Automatic Escalation via Frustrated Sentiment
        res1 = await client.post(
            f"/api/v1/support-copilot/portal/{portal_token}/chat",
            json={"message": "This is completely terrible and unacceptable service, I want to talk to a human manager now!"}
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["sentiment"] == "hostile"
        assert data1["is_escalated"] is True
        assert any(t["tool_name"] == "escalate_to_human" for t in data1["tool_calls"])

        # Check DB for HumanAssistanceRequest
        async with AsyncSessionLocal() as db:
            ticket = (await db.execute(select(HumanAssistanceRequest).where(HumanAssistanceRequest.client_id == client_id))).scalars().first()
            assert ticket is not None
            assert ticket.status == "pending"

        # 2. Explicit Escalation Endpoint
        res2 = await client.post(
            f"/api/v1/support-copilot/portal/{portal_token}/escalate",
            json={"reason": "Customer needs custom contractual volume discount review."}
        )
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["status"] == "escalated"
        assert "hitl_id" in data2

@pytest.mark.asyncio
async def test_crm_rep_management_and_takeover():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ctx = await setup_test_tenant_and_client(client)
        headers = ctx["headers"]
        portal_token = ctx["portal_token"]

        # 1. Customer initiates chat
        c_res = await client.post(
            f"/api/v1/support-copilot/portal/{portal_token}/chat",
            json={"message": "Hello, I am wondering about our discount on next month's volume."}
        )
        assert c_res.status_code == 200
        conv_id = c_res.json()["conversation_id"]

        # 2. Rep lists conversations in CRM console
        list_res = await client.get("/api/v1/support-copilot/conversations", headers=headers)
        assert list_res.status_code == 200
        conv_list = list_res.json()
        assert len(conv_list) >= 1
        matched = next((c for c in conv_list if c["id"] == conv_id), None)
        assert matched is not None
        assert matched["client_name"] == "Pacific Cascade Lumber"

        # 3. Rep inspects conversation detail
        detail_res = await client.get(f"/api/v1/support-copilot/conversations/{conv_id}", headers=headers)
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["conversation"]["id"] == conv_id
        assert len(detail["messages"]) >= 2

        # 4. Rep takes over and sends reply
        reply_res = await client.post(
            f"/api/v1/support-copilot/conversations/{conv_id}/reply",
            json={"message": "Hi Marcus, Sarah here. I have applied a 12% volume rebate to your next order.", "resolve_ticket": False},
            headers=headers
        )
        assert reply_res.status_code == 200
        rep_msg = reply_res.json()
        assert rep_msg["direction"] == "outbound"
        assert rep_msg["sender_type"] == "human_rep"
        assert "Sarah Jenkins" in rep_msg["sender_name"]

        # Verify portal history now shows rep's message
        hist_res = await client.get(f"/api/v1/support-copilot/portal/{portal_token}/history")
        assert hist_res.status_code == 200
        history_msgs = hist_res.json()
        assert any("Sarah here" in m["body_text"] for m in history_msgs)

        # 5. Rep resolves conversation
        resolve_res = await client.post(f"/api/v1/support-copilot/conversations/{conv_id}/resolve", headers=headers)
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "success"

        # Verify status updated
        detail_res2 = await client.get(f"/api/v1/support-copilot/conversations/{conv_id}", headers=headers)
        assert detail_res2.status_code == 200
        assert detail_res2.json()["conversation"]["status"] == "resolved"
