import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.tenant import Organization, OrganizationMembership, User
from app.models.crm import ClientAccount, ClientSale, SaaSLicense, Company
from app.models.procurement import PurchaseOrder, Supplier

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_executive_overview_metrics_calculation():
    """Verify executive KPI math: MRR, ARR, revenue, COGS, gross margin, net settlement, and ARPU."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register admin and organization
        reg = await client.post("/api/v1/auth/register", json={
            "email": "cfo@titanindustries.com",
            "password": "Password123!",
            "full_name": "Eleanor Vance",
            "organization_name": "Titan Industrial SaaS"
        })
        assert reg.status_code == 200
        admin_token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {admin_token}", "X-Organization-Id": org_id}

        # 2. Invite a sales rep
        invite = await client.post("/api/v1/team/invite", headers=headers, json={
            "email": "marcus.rep@titanindustries.com",
            "password": "Password123!",
            "full_name": "Marcus Kane",
            "role": "sales_rep"
        })
        assert invite.status_code == 200
        rep_user_id = invite.json()["user_id"]

        # 3. Populate database records directly
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            # Create Company
            company = Company(
                organization_id=org_id,
                name="AeroDynamics Corp",
                domain="aerodynamics.com",
                industry="Aerospace"
            )
            session.add(company)
            await session.flush()

            # Create ClientAccount with recurring cadence
            account = ClientAccount(
                organization_id=org_id,
                company_id=company.id,
                account_name="AeroDynamics Prime",
                status="active",
                total_revenue=2400.0,
                order_count=2,
                reorder_cadence_days=30,
                auto_charge_enabled=True
            )
            session.add(account)
            await session.flush()

            # Create Active SaaSLicense
            license_rec = SaaSLicense(
                organization_id=org_id,
                company_id=company.id,
                client_id=account.id,
                license_key="LIC-TITAN-PRO-001",
                product_name="Titan AI Logistics Suite",
                plan_tier="enterprise",
                license_status="active",
                billing_interval="monthly",
                licensed_seats=50,
                active_seats_used=35,
                mrr=800.0,
                arr=9600.0,
                contract_start_date=now - timedelta(days=60),
                renewal_date=now + timedelta(days=300),
                health_score=92,
                churn_risk_level="healthy"
            )
            session.add(license_rec)

            # Create Paid Client Sale attributed to Marcus Kane
            sale_paid = ClientSale(
                organization_id=org_id,
                client_id=account.id,
                order_number="SO-TITAN-1001",
                amount=2000.0,
                sale_date=now - timedelta(days=5),
                status="delivered",
                payment_method="credit_card",
                payment_status="paid",
                sales_rep_name="Marcus Kane",
                items_summary="50x Heavy Duty Valve Gaskets"
            )
            session.add(sale_paid)

            # Create Unpaid Client Sale
            sale_unpaid = ClientSale(
                organization_id=org_id,
                client_id=account.id,
                order_number="SO-TITAN-1002",
                amount=600.0,
                sale_date=now - timedelta(days=2),
                status="invoiced",
                payment_method="credit_terms_30",
                payment_status="unpaid",
                sales_rep_name="Marcus Kane",
                items_summary="20x Hydraulic Seal Kits"
            )
            session.add(sale_unpaid)

            # Create Supplier
            supplier = Supplier(
                organization_id=org_id,
                name="Grainger Industrial",
                code="grainger",
                website_url="https://www.grainger.com",
                category="Hydraulics"
            )
            session.add(supplier)
            await session.flush()

            # Create Purchase Order (COGS)
            po = PurchaseOrder(
                organization_id=org_id,
                po_number="PO-GRAINGER-9001",
                supplier_id=supplier.id,
                total_cost=800.0,
                status="delivered",
                currency="USD",
                placed_at=now - timedelta(days=4)
            )
            session.add(po)

            await session.commit()

        # 4. Fetch Executive Overview
        res = await client.get("/api/v1/executive/overview", headers=headers)
        assert res.status_code == 200
        data = res.json()

        # SaaSLicense MRR (800) + ClientAccount replenishment MRR (2400/2 * 30/30 = 1200) = 2000.0
        assert data["mrr"] == 2000.0
        assert data["arr"] == 24000.0
        assert data["total_collected_revenue"] == 2000.0
        assert data["total_unpaid_invoiced"] == 600.0
        assert data["total_supplier_cogs"] == 800.0
        
        # Gross profit = 2000.0 - 800.0 = 1200.0 (60.0% margin)
        assert data["gross_profit"] == 1200.0
        assert data["gross_margin_pct"] == 60.0

        # Rep commission = 10% of 2000.0 paid = 200.0
        assert data["total_commissions_earned"] == 200.0

        # Net settlement = 1200.0 - 200.0 = 1000.0 (50.0% net margin)
        assert data["net_settlement_margin"] == 1000.0
        assert data["net_margin_pct"] == 50.0

        assert data["active_client_accounts"] == 1
        assert data["arpu"] == 2000.0
        assert len(data["top_supplier_expenses"]) == 1
        assert data["top_supplier_expenses"][0]["supplier"] == "Grainger Industrial"
        assert data["top_supplier_expenses"][0]["total_spend"] == 800.0

@pytest.mark.asyncio
async def test_financial_reconciliation_statement_and_discrepancies():
    """Verify structured financial reconciliation ledger assembling client receipts, supplier COGS, and commissions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Register admin
        reg = await client.post("/api/v1/auth/register", json={
            "email": "controller@apexsupply.com",
            "password": "Password123!",
            "full_name": "Rachel Zane",
            "organization_name": "Apex Supply"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            comp = Company(organization_id=org_id, name="Test Company")
            session.add(comp)
            await session.flush()

            acc = ClientAccount(organization_id=org_id, company_id=comp.id, account_name="Test Account")
            session.add(acc)
            await session.flush()

            # Old unpaid sale (35 days old) -> Should trigger discrepancy
            sale_old = ClientSale(
                organization_id=org_id,
                client_id=acc.id,
                order_number="SO-APEX-OLD",
                amount=500.0,
                sale_date=now - timedelta(days=35),
                payment_status="unpaid",
                status="invoiced",
                items_summary="Late invoice test"
            )
            # Paid sale
            sale_paid = ClientSale(
                organization_id=org_id,
                client_id=acc.id,
                order_number="SO-APEX-PAID",
                amount=1500.0,
                sale_date=now - timedelta(days=2),
                payment_status="paid",
                status="completed",
                sales_rep_name="Rachel Zane",
                items_summary="Recent paid deal"
            )
            session.add_all([sale_old, sale_paid])

            sup = Supplier(
                organization_id=org_id,
                name="Amazon Business",
                code="amazon",
                website_url="https://business.amazon.com"
            )
            session.add(sup)
            await session.flush()

            po = PurchaseOrder(
                organization_id=org_id,
                po_number="PO-AMZ-01",
                supplier_id=sup.id,
                total_cost=600.0,
                status="shipped",
                placed_at=now - timedelta(days=1)
            )
            session.add(po)
            await session.commit()

        # Query reconciliation
        res = await client.get("/api/v1/executive/reconciliation", headers=headers)
        assert res.status_code == 200
        rec = res.json()

        assert rec["total_revenue"] == 1500.0
        assert rec["total_cogs"] == 600.0
        assert rec["total_commissions"] == 150.0  # 10% of 1500
        assert rec["net_settlement"] == 750.0  # 1500 - 600 - 150
        assert rec["unsettled_discrepancies_count"] >= 1  # Old unpaid invoice

        types = [item["transaction_type"] for item in rec["line_items"]]
        assert "client_sale_paid" in types
        assert "rep_commission" in types
        assert "supplier_po_cost" in types
        assert "client_sale_invoiced" in types

@pytest.mark.asyncio
async def test_reconciliation_rfc4180_csv_export():
    """Verify downloading RFC 4180 CSV attachment stream with columns and totals."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "finance@metrixcorp.com",
            "password": "Password123!",
            "full_name": "Jordan Bell",
            "organization_name": "Metrix Corp"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        csv_res = await client.get("/api/v1/executive/reconciliation/export", headers=headers)
        assert csv_res.status_code == 200
        assert "text/csv" in csv_res.headers.get("content-type", "")
        assert "attachment; filename=" in csv_res.headers.get("content-disposition", "")

        content = csv_res.text
        assert "# Executive Financial Reconciliation Statement" in content
        assert "Date,Transaction Type,Reference ID,Client or Vendor,Revenue ($),COGS ($),Commission ($),Net Settlement ($),Payment Method,Status" in content
        assert "SUMMARY TOTALS" in content

@pytest.mark.asyncio
async def test_sales_rep_commission_ledger_and_rate_updates():
    """Verify calculating rep commissions and allowing managers to adjust rates with audit tracking."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        reg = await client.post("/api/v1/auth/register", json={
            "email": "vp_sales@velocity.com",
            "password": "Password123!",
            "full_name": "Sarah Connor",
            "organization_name": "Velocity Systems"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # Invite sales rep
        inv = await client.post("/api/v1/team/invite", headers=headers, json={
            "email": "rep_dan@velocity.com",
            "password": "Password123!",
            "full_name": "Dan Cooper",
            "role": "sales_rep"
        })
        assert inv.status_code == 200
        rep_id = inv.json()["user_id"]

        # Add paid sale for Dan Cooper
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            comp = Company(organization_id=org_id, name="Client Co")
            session.add(comp)
            await session.flush()

            acc = ClientAccount(organization_id=org_id, company_id=comp.id, account_name="Client Acct")
            session.add(acc)
            await session.flush()

            sale = ClientSale(
                organization_id=org_id,
                client_id=acc.id,
                order_number="SO-VEL-55",
                amount=3000.0,
                sale_date=now,
                payment_status="paid",
                status="completed",
                sales_rep_name="Dan Cooper",
                items_summary="Enterprise Software Package"
            )
            session.add(sale)
            await session.commit()

        # Fetch commission leaderboard (default 10% rate)
        comms_res = await client.get("/api/v1/executive/commissions", headers=headers)
        assert comms_res.status_code == 200
        board = comms_res.json()
        assert board["total_sales_volume"] == 3000.0
        assert board["total_commissions_payable"] == 300.0  # 10% of 3000

        dan_entry = [r for r in board["reps"] if r["user_id"] == rep_id][0]
        assert dan_entry["commission_earned"] == 300.0
        assert dan_entry["commission_rate_pct"] == 10.0

        # Update Dan's commission rate to 15%
        patch_res = await client.patch(f"/api/v1/executive/commissions/{rep_id}", headers=headers, json={
            "commission_rate_pct": 15.0
        })
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["commission_rate_pct"] == 15.0
        assert updated["commission_earned"] == 450.0  # 15% of 3000

        # Verify leaderboard reflects update
        comms_updated = await client.get("/api/v1/executive/commissions", headers=headers)
        assert comms_updated.json()["total_commissions_payable"] == 450.0

@pytest.mark.asyncio
async def test_executive_rbac_permission_enforcement():
    """Verify RBAC: admin, sales_manager, billing_officer allowed; sales_rep and viewer receive 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Admin
        reg = await client.post("/api/v1/auth/register", json={
            "email": "ceo@securitycorp.com",
            "password": "Password123!",
            "full_name": "Chief Executive",
            "organization_name": "Security Corp"
        })
        admin_token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        admin_headers = {"Authorization": f"Bearer {admin_token}", "X-Organization-Id": org_id}

        # Invite Sales Rep
        inv_rep = await client.post("/api/v1/team/invite", headers=admin_headers, json={
            "email": "rep@securitycorp.com",
            "password": "Password123!",
            "full_name": "Junior Rep",
            "role": "sales_rep"
        })
        assert inv_rep.status_code == 200
        login_rep = await client.post("/api/v1/auth/login", json={
            "email": "rep@securitycorp.com",
            "password": "Password123!"
        })
        assert login_rep.status_code == 200
        rep_token = login_rep.json()["access_token"]
        rep_headers = {"Authorization": f"Bearer {rep_token}", "X-Organization-Id": org_id}

        # Invite Viewer
        inv_viewer = await client.post("/api/v1/team/invite", headers=admin_headers, json={
            "email": "intern@securitycorp.com",
            "password": "Password123!",
            "full_name": "Intern Viewer",
            "role": "viewer"
        })
        assert inv_viewer.status_code == 200
        login_viewer = await client.post("/api/v1/auth/login", json={
            "email": "intern@securitycorp.com",
            "password": "Password123!"
        })
        assert login_viewer.status_code == 200
        viewer_token = login_viewer.json()["access_token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}", "X-Organization-Id": org_id}

        # Invite Billing Officer
        inv_billing = await client.post("/api/v1/team/invite", headers=admin_headers, json={
            "email": "billing@securitycorp.com",
            "password": "Password123!",
            "full_name": "Billing Clerk",
            "role": "billing_officer"
        })
        assert inv_billing.status_code == 200
        login_billing = await client.post("/api/v1/auth/login", json={
            "email": "billing@securitycorp.com",
            "password": "Password123!"
        })
        assert login_billing.status_code == 200
        billing_token = login_billing.json()["access_token"]
        billing_headers = {"Authorization": f"Bearer {billing_token}", "X-Organization-Id": org_id}

        # 1. Sales rep forbidden from executive overview
        rep_overview = await client.get("/api/v1/executive/overview", headers=rep_headers)
        assert rep_overview.status_code == 403

        # 2. Viewer forbidden from executive overview
        viewer_overview = await client.get("/api/v1/executive/overview", headers=viewer_headers)
        assert viewer_overview.status_code == 403

        # 3. Billing Officer permitted to view overview
        billing_overview = await client.get("/api/v1/executive/overview", headers=billing_headers)
        assert billing_overview.status_code == 200

        # 4. Billing Officer NOT permitted to change rep commission rates (only admin & sales_manager)
        billing_patch = await client.patch(
            f"/api/v1/executive/commissions/{inv_rep.json()['user_id']}",
            headers=billing_headers,
            json={"commission_rate_pct": 20.0}
        )
        assert billing_patch.status_code == 403
