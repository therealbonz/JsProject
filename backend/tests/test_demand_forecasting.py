import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from main import app
from app.core.database import engine, Base, AsyncSessionLocal
from app.models.crm import ClientAccount, ClientSale, DemandForecastLog
from app.services.demand_forecast_service import DemandForecastService

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

def test_statistical_burn_rate_and_safety_stock_calculation():
    """
    Direct unit test for DemandForecastService._calculate_statistical_metrics
    evaluating consumption intervals, daily burn rate, and dynamic safety stock buffer.
    """
    now = datetime.now(timezone.utc)
    client = ClientAccount(
        account_name="Titan Robotics Corp",
        reorder_cadence_days=30,
        status="active"
    )

    # 3 historical sales: 30 days apart, amounts $1500, $1650, $1550
    s1 = ClientSale(order_number="SO-1", amount=1500.0, sale_date=now - timedelta(days=60), status="completed")
    s2 = ClientSale(order_number="SO-2", amount=1650.0, sale_date=now - timedelta(days=30), status="completed")
    s3 = ClientSale(order_number="SO-3", amount=1550.0, sale_date=now - timedelta(days=5), status="completed")

    metrics = DemandForecastService._calculate_statistical_metrics(
        client=client,
        sales=[s3, s2, s1],
        lead_time_days=7,
        service_level_z=1.65
    )

    assert metrics["burn_rate"] > 40.0
    assert metrics["avg_amount"] > 1500.0
    assert metrics["avg_interval"] >= 25.0
    assert 10.0 <= metrics["safety_stock_buffer_percent"] <= 35.0
    assert metrics["recommended_amount"] > metrics["avg_amount"]
    assert metrics["stockout_risk_score"] >= 0
    assert metrics["stockout_risk_level"] in ("low", "moderate", "high", "critical")
    assert metrics["recommended_reorder_date"] is not None

@pytest.mark.asyncio
async def test_generate_forecast_for_client_and_db_persistence():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant
        reg = await client.post("/api/v1/auth/register", json={
            "email": "lead@aerodynamicssupply.example",
            "password": "SecurePassword123!",
            "full_name": "Howard Hughes",
            "organization_name": "Aerodynamics Supply Group"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        # 2. Create client account
        c_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Vortex Aerospace Technologies",
            "contact_first_name": "Alan",
            "contact_last_name": "Shepard",
            "contact_email": "alan@vortextest.example",
            "reorder_cadence_days": 21,
            "status": "active"
        }, headers=headers)
        client_id = c_res.json()["id"]

        # 3. Log 2 sales for client to establish consumption velocity
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            s1 = ClientSale(
                organization_id=org_id,
                client_id=client_id,
                order_number="SO-VTX-01",
                amount=2400.0,
                sale_date=now - timedelta(days=40),
                status="completed",
                payment_status="paid",
                items_summary="High-grade turbine titanium bolts"
            )
            s2 = ClientSale(
                organization_id=org_id,
                client_id=client_id,
                order_number="SO-VTX-02",
                amount=2600.0,
                sale_date=now - timedelta(days=19),
                status="completed",
                payment_status="paid",
                items_summary="High-grade turbine titanium bolts"
            )
            db.add_all([s1, s2])
            c_acc = await db.get(ClientAccount, client_id)
            c_acc.total_revenue = 5000.0
            c_acc.order_count = 2
            await db.commit()

            # Execute DemandForecastService directly
            forecast = await DemandForecastService.generate_forecast_for_client(
                db=db,
                org_id=org_id,
                client_id=client_id
            )

        assert forecast["client_id"] == client_id
        assert forecast["predicted_burn_rate"] > 80.0
        assert forecast["safety_stock_buffer_percent"] >= 10.0
        assert forecast["stockout_risk_score"] > 0
        assert forecast["forecast_confidence"] >= 0.80
        assert len(forecast["forecast_rationale"]) > 15
        assert forecast["recommended_restock_amount"] > 2500.0

        # Verify persisted on ClientAccount
        async with AsyncSessionLocal() as db:
            c = await db.get(ClientAccount, client_id)
            assert c.predicted_burn_rate == forecast["predicted_burn_rate"]
            assert c.stockout_risk_score == forecast["stockout_risk_score"]
            assert c.stockout_risk_level == forecast["stockout_risk_level"]
            assert c.forecast_rationale == forecast["forecast_rationale"]

            # Verify historical log entry created
            log_stmt = select(DemandForecastLog).where(DemandForecastLog.client_id == client_id)
            log_res = await db.execute(log_stmt)
            logs = log_res.scalars().all()
            assert len(logs) == 1
            assert logs[0].predicted_burn_rate == forecast["predicted_burn_rate"]

@pytest.mark.asyncio
async def test_forecasting_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant and client
        reg = await client.post("/api/v1/auth/register", json={
            "email": "ops@solarenergylabs.example",
            "password": "SecurePassword123!",
            "full_name": "Nikola Vance",
            "organization_name": "Solar Energy Labs"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        c_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Helios Inverters & Cells",
            "contact_first_name": "Claire",
            "contact_last_name": "Dupont",
            "contact_email": "claire@heliostest.example",
            "reorder_cadence_days": 30,
            "status": "active"
        }, headers=headers)
        client_id = c_res.json()["id"]

        # 2. GET /crm/forecasting/overview
        ov_res = await client.get("/api/v1/crm/forecasting/overview", headers=headers)
        assert ov_res.status_code == 200
        ov_data = ov_res.json()
        assert ov_data["monitored_accounts"] >= 1
        assert "average_burn_rate" in ov_data
        assert "projected_30d_demand" in ov_data

        # 3. GET /crm/clients/{client_id}/forecast
        f_res = await client.get(f"/api/v1/crm/clients/{client_id}/forecast", headers=headers)
        assert f_res.status_code == 200
        f_data = f_res.json()
        assert f_data["client_id"] == client_id
        assert f_data["safety_stock_buffer_percent"] >= 10.0
        assert f_data["stockout_risk_score"] >= 0

        # 4. POST /crm/clients/{client_id}/forecast/refresh
        rf_res = await client.post(f"/api/v1/crm/clients/{client_id}/forecast/refresh", headers=headers)
        assert rf_res.status_code == 200
        assert rf_res.json()["client_id"] == client_id

        # 5. POST /crm/clients/{client_id}/apply-forecast-cadence
        adopt_res = await client.post(f"/api/v1/crm/clients/{client_id}/apply-forecast-cadence", json={
            "apply_cadence_days": True,
            "apply_reorder_date": True
        }, headers=headers)
        assert adopt_res.status_code == 200
        adopt_data = adopt_res.json()
        assert adopt_data["success"] is True
        assert adopt_data["next_reorder_date"] is not None

@pytest.mark.asyncio
async def test_customer_portal_telemetry_integration():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Register tenant and client
        reg = await client.post("/api/v1/auth/register", json={
            "email": "director@pacificdefense.example",
            "password": "SecurePassword123!",
            "full_name": "Marcus Wright",
            "organization_name": "Pacific Defense Dynamics"
        })
        token = reg.json()["access_token"]
        org_id = reg.json()["organization_id"]
        headers = {"Authorization": f"Bearer {token}", "X-Organization-Id": org_id}

        c_res = await client.post("/api/v1/crm/clients", json={
            "account_name": "Kodiak Naval Logistics",
            "contact_first_name": "Sarah",
            "contact_last_name": "Connor",
            "contact_email": "sarah@kodiaknavy.example",
            "reorder_cadence_days": 30,
            "status": "active"
        }, headers=headers)
        client_id = c_res.json()["id"]

        # Run forecast first
        await client.post(f"/api/v1/crm/clients/{client_id}/forecast/refresh", headers=headers)

        # Generate customer portal magic link
        link_res = await client.post(f"/api/v1/crm/clients/{client_id}/portal-link", headers=headers)
        portal_token = link_res.json()["portal_access_token"]

        # 2. Public / Passwordless session loader includes inventory telemetry
        sess_res = await client.get(f"/api/v1/portal/session/{portal_token}")
        assert sess_res.status_code == 200
        sess_data = sess_res.json()
        assert "inventory_telemetry" in sess_data
        telemetry = sess_data["inventory_telemetry"]
        assert "predicted_burn_rate" in telemetry
        assert "stockout_risk_score" in telemetry
        assert "stockout_risk_level" in telemetry
        assert "safety_stock_buffer_percent" in telemetry
        assert "forecast_rationale" in telemetry

        # 3. Portal HTML page contains telemetry advisory card
        page_res = await client.get(f"/portal/{portal_token}")
        assert page_res.status_code == 200
        assert "AI Inventory Telemetry &amp; Safety Stock Advisory" in page_res.text
        assert "telemetry-risk-badge" in page_res.text
