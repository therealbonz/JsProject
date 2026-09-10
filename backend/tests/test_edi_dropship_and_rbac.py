import pytest
import pytest_asyncio
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.procurement import Supplier, PurchaseOrder, ShipmentTracking
from app.models.crm import ClientAccount, ClientSale
from app.models.tenant import OrganizationMembership, User
from app.models.hitl import AuditLog

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_edi_850_generation_and_export():
    """Test generating standard ANSI ASC X12 EDI 850 text and REST dropship JSON payload."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "edimanager@nexuslogistics.com",
            "password": "Password123!",
            "full_name": "David Miller",
            "organization_name": "Nexus Logistics B2B"
        })
        assert reg.status_code == 200
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Trigger autofill order to generate purchase order with items
        po_fill = await client.post("/api/v1/fulfillment/autofill", headers=headers, json={
            "requirement_prompt": "Order 15 cases of industrial air filters",
            "destination_type": "customer_dropship",
            "destination_address": "850 Industrial Parkway, Dock 3, Chicago IL 60601",
            "max_budget_limit": 1000.0
        })
        assert po_fill.status_code == 200
        po_id = po_fill.json()["purchase_order_id"]
        po_num = po_fill.json()["po_number"]

        # 3. Request EDI 850 Document
        edi_res = await client.get(f"/api/v1/fulfillment/orders/{po_id}/edi-850", headers=headers)
        assert edi_res.status_code == 200
        edi_data = edi_res.json()

        assert edi_data["po_id"] == po_id
        assert edi_data["po_number"] == po_num
        assert edi_data["destination_type"] == "customer_dropship"
        assert edi_data["destination_address"] == "850 Industrial Parkway, Dock 3, Chicago IL 60601"

        # Verify ANSI ASC X12 structure
        x12 = edi_data["edi_x12_payload"]
        assert "ISA*00*" in x12
        assert "GS*PO*" in x12
        assert "ST*850*0001~" in x12
        assert f"BEG*00*SA*{po_num}" in x12
        assert "N1*ST*Customer Destination*" in x12
        assert "PO1*1*" in x12
        assert "CTT*" in x12
        assert "SE*" in x12
        assert "GE*1*" in x12
        assert "IEA*1*" in x12

        # Verify JSON dropship payload
        dropship = edi_data["dropship_json_payload"]
        assert dropship["edi_document"] == "850"
        assert dropship["po_number"] == po_num
        assert len(dropship["line_items"]) > 0
        assert dropship["purchaser"]["organization_id"] == org_id

        # 4. Dispatch EDI 850 Order
        dispatch_res = await client.post(f"/api/v1/fulfillment/orders/{po_id}/dispatch-edi", headers=headers)
        assert dispatch_res.status_code == 200
        disp_data = dispatch_res.json()
        assert disp_data["success"] is True
        assert disp_data["status"] == "acknowledged_by_vendor"
        assert "transmission_id" in disp_data

@pytest.mark.asyncio
async def test_edi_856_asn_webhook_ingestion_and_tracking_sync():
    """Test receiving real-time EDI 856 ASN webhook and syncing shipment tracking & client sale."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "fulfillment@apexsupplies.com",
            "password": "Password123!",
            "full_name": "Carlos Rivera",
            "organization_name": "Apex Supplies Corp"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # Create Client Account and Sale
        client_res = await client.post("/api/v1/crm/clients", headers=headers, json={
            "account_name": "Sterling Aerospace",
            "contact_first_name": "Jack",
            "contact_last_name": "Lawson",
            "contact_email": "jack@sterlingaero.com",
            "reorder_cadence_days": 30
        })
        assert client_res.status_code == 200
        client_id = client_res.json()["id"]

        sale_res = await client.post(f"/api/v1/crm/clients/{client_id}/sales", headers=headers, json={
            "amount": 1850.0,
            "items_summary": "Titanium Bolt Assembly & Sealants",
            "customer_email": "jack@sterlingaero.com",
            "shipping_address": "400 Aviation Way, Hangar 9, Seattle WA"
        })
        sale_id = sale_res.json()["id"]
        sale_order_num = sale_res.json()["order_number"]

        # Place linked Purchase Order via autofill
        fill_res = await client.post("/api/v1/fulfillment/autofill", headers=headers, json={
            "requirement_prompt": "10 packs of titanium bolts",
            "destination_type": "customer_dropship",
            "destination_address": "400 Aviation Way, Hangar 9, Seattle WA",
            "client_sale_id": sale_id,
            "max_budget_limit": 2000.0
        })
        po_id = fill_res.json()["purchase_order_id"]
        po_num = fill_res.json()["po_number"]

        # Ingest incoming EDI 856 Advance Ship Notice (ASN) Webhook
        asn_payload = {
            "po_number": po_num,
            "supplier_code": "grainger",
            "carrier": "FedEx",
            "tracking_number": "794689234109",
            "tracking_url": "https://www.fedex.com/fedextrack/?trknbr=794689234109",
            "shipment_status": "in_transit",
            "current_location": "Memphis Regional Logistics Facility, TN",
            "status_event_description": "Scanned into transit network and loaded on delivery transport"
        }
        asn_res = await client.post("/api/v1/fulfillment/edi-856/webhook", headers=headers, json=asn_payload)
        assert asn_res.status_code == 200
        receipt = asn_res.json()
        assert receipt["success"] is True
        assert receipt["po_number"] == po_num
        assert receipt["carrier"] == "FEDEX"
        assert receipt["tracking_number"] == "794689234109"
        assert receipt["shipment_status"] == "in_transit"
        assert receipt["updated_sale_id"] == sale_id

        # Verify PurchaseOrder in DB
        async with AsyncSessionLocal() as session:
            po_stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
            po_db = (await session.execute(po_stmt)).scalar_one()
            assert po_db.status == "in_transit"

            # Verify ShipmentTracking created
            track_stmt = select(ShipmentTracking).where(ShipmentTracking.purchase_order_id == po_id)
            track_db = (await session.execute(track_stmt)).scalar_one()
            assert track_db.carrier == "FEDEX"
            assert track_db.tracking_number == "794689234109"
            assert track_db.current_status == "in_transit"
            assert len(track_db.history_events) >= 1

            # Verify ClientSale exists and is linked
            sale_stmt = select(ClientSale).where(ClientSale.id == sale_id)
            sale_db = (await session.execute(sale_stmt)).scalar_one()
            assert sale_db.id == sale_id

        # Now test the console simulation endpoint with delivery status
        sim_res = await client.post("/api/v1/fulfillment/edi-856/simulate", headers=headers, json={
            "po_id": po_id,
            "carrier": "FedEx",
            "shipment_status": "delivered",
            "current_location": "Customer Hangar 9 Delivery Dock, Seattle WA",
            "status_event_description": "Delivered and signed by J. Lawson"
        })
        assert sim_res.status_code == 200
        assert sim_res.json()["shipment_status"] == "delivered"

        # Verify delivered state persisted
        async with AsyncSessionLocal() as session:
            po_stmt = select(PurchaseOrder).where(PurchaseOrder.id == po_id)
            po_db = (await session.execute(po_stmt)).scalar_one()
            assert po_db.status == "delivered"

            track_stmt = select(ShipmentTracking).where(ShipmentTracking.purchase_order_id == po_id)
            track_db = (await session.execute(track_stmt)).scalar_one()
            assert track_db.current_status == "delivered"
            assert track_db.actual_delivery is not None

            sale_stmt = select(ClientSale).where(ClientSale.id == sale_id)
            sale_db = (await session.execute(sale_stmt)).scalar_one()
            assert sale_db.status == "delivered"

@pytest.mark.asyncio
async def test_team_invite_role_update_and_last_admin_guardrail():
    """Test team member invitations, role mutations, and last administrator protection."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register admin
        reg = await client.post("/api/v1/auth/register", json={
            "email": "primaryadmin@globalmro.com",
            "password": "Password123!",
            "full_name": "Victoria Stone",
            "organization_name": "Global MRO Distributing"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Check roles list
        roles_res = await client.get("/api/v1/team/roles", headers=headers)
        assert roles_res.status_code == 200
        roles_data = roles_res.json()
        assert len(roles_data) >= 6
        role_keys = [r["role"] for r in roles_data]
        assert "admin" in role_keys
        assert "sales_manager" in role_keys
        assert "fulfillment_specialist" in role_keys
        assert "billing_officer" in role_keys

        # 3. Invite a Fulfillment Specialist
        inv1 = await client.post("/api/v1/team/invite", headers=headers, json={
            "email": "lucas@globalmro.com",
            "full_name": "Lucas Gray",
            "role": "fulfillment_specialist",
            "password": "TemporarySecret123!"
        })
        assert inv1.status_code == 200
        mem1 = inv1.json()
        assert mem1["role"] == "fulfillment_specialist"
        assert mem1["email"] == "lucas@globalmro.com"
        mem1_id = mem1["id"]

        # 4. List team members
        members_res = await client.get("/api/v1/team/members", headers=headers)
        assert members_res.status_code == 200
        members = members_res.json()
        assert len(members) == 2  # Victoria (admin) + Lucas (fulfillment_specialist)

        # 5. Update Lucas's role to sales_manager
        patch_res = await client.patch(f"/api/v1/team/members/{mem1_id}", headers=headers, json={
            "role": "sales_manager"
        })
        assert patch_res.status_code == 200
        assert patch_res.json()["role"] == "sales_manager"

        # 6. Test Last-Admin Guardrail: Attempt to demote Victoria (the sole admin) to viewer
        # First get Victoria's membership id
        vic_mem = next(m for m in members if m["email"] == "primaryadmin@globalmro.com")
        demote_res = await client.patch(f"/api/v1/team/members/{vic_mem['id']}", headers=headers, json={
            "role": "viewer"
        })
        assert demote_res.status_code == 400
        assert "Cannot demote the sole remaining Administrator" in demote_res.json()["detail"]

        # 7. Delete Lucas from the team
        del_res = await client.delete(f"/api/v1/team/members/{mem1_id}", headers=headers)
        assert del_res.status_code == 200
        assert del_res.json()["success"] is True

        # Verify 1 member remaining
        members_res2 = await client.get("/api/v1/team/members", headers=headers)
        assert len(members_res2.json()) == 1

@pytest.mark.asyncio
async def test_rbac_permission_scope_enforcement():
    """Verify route authorization enforcement: non-admins are blocked from administrative routes."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register Organization with Admin
        reg = await client.post("/api/v1/auth/register", json={
            "email": "corpadmin@securityhub.com",
            "password": "Password123!",
            "full_name": "Chief Admin",
            "organization_name": "Security Scoped Corp"
        })
        admin_token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Organization-Id": org_id}

        # Invite a Sales Rep user
        await client.post("/api/v1/team/invite", headers=admin_headers, json={
            "email": "rep@securityhub.com",
            "full_name": "Junior Sales Rep",
            "role": "sales_rep",
            "password": "RepPassword123!"
        })

        # Login as Sales Rep
        rep_login = await client.post("/api/v1/auth/login", json={
            "email": "rep@securityhub.com",
            "password": "RepPassword123!"
        })
        assert rep_login.status_code == 200
        rep_token = rep_login.json()["access_token"]
        rep_headers = {"Authorization": f"Bearer {rep_token}", "X-Organization-Id": org_id}

        # 1. Sales Rep CAN access read-only /team/members
        mem_check = await client.get("/api/v1/team/members", headers=rep_headers)
        assert mem_check.status_code == 200

        # 2. Sales Rep CANNOT invite other team members (admin required)
        forbidden_invite = await client.post("/api/v1/team/invite", headers=rep_headers, json={
            "email": "intruder@securityhub.com",
            "full_name": "Intruder",
            "role": "sales_rep"
        })
        assert forbidden_invite.status_code == 403
        assert "Access denied" in forbidden_invite.json()["detail"]
        assert "'sales_rep'" in forbidden_invite.json()["detail"]

        # 3. Sales Rep CANNOT dispatch EDI purchase orders (admin or fulfillment_specialist required)
        # Create a dummy PO with admin
        po_res = await client.post("/api/v1/fulfillment/autofill", headers=admin_headers, json={
            "requirement_prompt": "5 safety helmets",
            "max_budget_limit": 500.0
        })
        dummy_po_id = po_res.json()["purchase_order_id"]

        forbidden_edi = await client.post(f"/api/v1/fulfillment/orders/{dummy_po_id}/dispatch-edi", headers=rep_headers)
        assert forbidden_edi.status_code == 403

        # 4. Admin CAN successfully dispatch EDI
        allowed_edi = await client.post(f"/api/v1/fulfillment/orders/{dummy_po_id}/dispatch-edi", headers=admin_headers)
        assert allowed_edi.status_code == 200

@pytest.mark.asyncio
async def test_immutable_audit_logging_and_csv_export():
    """Verify system-wide audit event recording, multi-dimensional queries, overview metrics, and CSV export."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "auditor@defensesupply.com",
            "password": "Password123!",
            "full_name": "Auditor General",
            "organization_name": "Defense Supply Solutions"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # Perform audited actions
        # Action 1: Invite a member
        await client.post("/api/v1/team/invite", headers=headers, json={
            "email": "officer@defensesupply.com",
            "full_name": "Finance Officer",
            "role": "billing_officer",
            "password": "Password123!"
        })

        # Action 2: Autofill order
        po_res = await client.post("/api/v1/fulfillment/autofill", headers=headers, json={
            "requirement_prompt": "20 rugged ethernet cables",
            "max_budget_limit": 500.0
        })
        po_id = po_res.json()["purchase_order_id"]

        # Action 3: Inspect EDI 850 (triggers edi.850_generated audit event)
        await client.get(f"/api/v1/fulfillment/orders/{po_id}/edi-850", headers=headers)

        # 1. Query Audit Logs endpoint
        logs_res = await client.get("/api/v1/team/audit-logs", headers=headers)
        assert logs_res.status_code == 200
        logs = logs_res.json()
        assert len(logs) >= 2
        actions = [l["action"] for l in logs]
        assert "team.member_invited" in actions
        assert "edi.850_generated" in actions

        # Check enriched metadata
        team_log = next(l for l in logs if l["action"] == "team.member_invited")
        assert team_log["actor_email"] == "auditor@defensesupply.com"
        assert team_log["actor_role"] == "admin"
        assert team_log["status"] == "success"

        # 2. Query Audit Overview endpoint
        overview_res = await client.get("/api/v1/team/audit-logs/overview", headers=headers)
        assert overview_res.status_code == 200
        overview = overview_res.json()
        assert overview["total_events"] >= 2
        assert "team" in overview["actions_breakdown"] or "edi" in overview["actions_breakdown"]

        # 3. Export Audit Logs as CSV
        csv_res = await client.get("/api/v1/team/audit-logs/export?format=csv", headers=headers)
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers.get("content-type", "")
        csv_text = csv_res.text
        assert "Timestamp (UTC),Actor Type,Actor Email,Actor Role,Action" in csv_text
        assert "auditor@defensesupply.com" in csv_text
        assert "team.member_invited" in csv_text
